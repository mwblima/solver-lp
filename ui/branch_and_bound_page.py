import streamlit as st
import pandas as pd
import numpy as np # Adicionado para tratar tipos do numpy na formatação

from .helpers import _store_problem, _load_problem, number_emojis
from core.branch_bound_solver import BranchBoundSolver
from ui.lang import t

def bab_ui():
    st.markdown(f"<h1 style='text-align: center;'>{t('bab.title')}</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; color: #888;'>{t('bab.subtitle')}</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # Exibir toast de redirecionamento (vindo do Simplex)
    if "pending_toast" in st.session_state:
        st.toast(st.session_state.pop("pending_toast"), icon="ℹ️")

    # Carregar estado anterior se existir
    saved = st.session_state.get("problem", {})
    saved_c, saved_A, saved_b = saved.get("c", []), saved.get("A", []), saved.get("b", [])
    saved_int = saved.get("int_vars", [])
    saved_var_types = saved.get("var_types", [])

    # Layout de entrada similar ao Simplex
    col_counts = st.columns(3)
    with col_counts[0]:
        n_vars = st.number_input(t("simplex.n_vars"), 2, 10, max(len(saved_c), 2), help=t("simplex.vars_help"))
    with col_counts[1]:
        n_cons = st.number_input(t("simplex.n_cons"), 1, 10, max(len(saved_A), 1), help=t("simplex.cons_help"))
        
    with col_counts[2]:
        maximize = st.selectbox(
            t("simplex.obj_type"), 
            [t("simplex.maximize"), t("simplex.minimize")], 
            index=0 if saved.get("maximize", True) else 1
        )
        is_max = (maximize == t("simplex.maximize"))

    # Função objetivo
    label_obj = t("common.obj_max") if is_max else t("common.obj_min")
    st.markdown(f"#### {label_obj}", help=t("simplex.obj_help"))
    
    # Variable type options
    type_options = [t("simplex.var_real"), t("simplex.var_integer"), t("simplex.var_binary")]
    
    obj_cols = st.columns(n_vars)
    c = []
    var_types = []
    int_vars = []
    binary_vars = []
    for i in range(n_vars):
        default = saved_c[i] if i < len(saved_c) else 1.0
        # Default type from saved var_types, then from int_vars, fallback to Integer
        if i < len(saved_var_types):
            vt_map = {"real": 0, "integer": 1, "binary": 2}
            default_type_idx = vt_map.get(saved_var_types[i], 1)
        elif saved_int:
            default_type_idx = 1 if (i in saved_int) else 0
        else:
            default_type_idx = 1  # Default to Integer for B&B page
        with obj_cols[i]:
            # Type selector
            vtype = st.selectbox(
                f"{t('simplex.var_type')} x{i+1}",
                type_options,
                index=default_type_idx,
                key=f"bb_vtype_{i}",
                label_visibility="collapsed"
            )
            var_types.append(vtype)
            
            # The coefficient input is independent of the variable domain
            val = st.number_input(f"**x{i+1}**", value=float(default), key=f"bb_c_{i}", help=f"{t('simplex.coef_help')} x{i+1}")
            
            # Track integer and binary variables
            if vtype == t("simplex.var_binary"):
                int_vars.append(i)
                binary_vars.append(i)
            elif vtype == t("simplex.var_integer"):
                int_vars.append(i)
                
            c.append(val)

    # Restrições
    # Restrições
    with st.expander(t("simplex.constraints"), expanded=True):
        
        A, b = [], []
        senses = []
        for r in range(n_cons):
            st.markdown(f"**{t('common.restriction')}  - {number_emojis[r+1]}:**")
            cols = st.columns(n_vars + 2)
            row = []
            
            for i in range(n_vars):
                default = saved_A[r][i] if r < len(saved_A) and i < len(saved_A[r]) else 1.0
                with cols[i]:
                    row.append(st.number_input(f"**x{i+1}**", key=f"bb_a_{r}_{i}", value=default, help=f"{t('simplex.coef_help')} x{i+1}"))
            
            with cols[n_vars]:
                sense = st.selectbox(t("simplex.type_label"), ["≤", "=", "≥"], index=0, key=f"bb_sense_{r}")
                
            with cols[n_vars+1]:
                default_rhs = saved_b[r] if r < len(saved_b) else 1.0
                rhs = st.number_input(t("simplex.rhs_label"), key=f"bb_b_{r}", value=default_rhs, help=f"Valor do lado direito")
            
            A.append(row)
            b.append(rhs)
            senses.append(sense)

    # Seleção de variáveis inteiras


    # Botão resolver
    
    # Controles de Execução (Estratégia, Modo e Botão na mesma linha)
    
    col_strat, col_mode, col_btn = st.columns([3, 2, 2], gap="medium")
    
    with col_strat:
        strategy_options = {
            t("bab.strats.BFS"): "BFS",
            t("bab.strats.DFS"): "DFS",
            t("bab.strats.BestBound"): "BestBound"
        }
        
        selected_strategy_label = st.selectbox(
            t("bab.strategy"),
            list(strategy_options.keys()),
            index=0,
            help=t("bab.strat_help")
        )
        selected_strategy = strategy_options.get(selected_strategy_label, "BFS")

    with col_mode:
        # Espaçamento para alinhar com o input
        st.write("")
        st.write("")
        step_by_step = st.checkbox(t("simplex.step_by_step"), value=False, help="Executar nó a nó.")

    with col_btn:
        # Espaçamento para alinhar com o input
        st.write("")
        st.write("")
        solve_clicked = st.button(t("bab.btn_start"), type="primary", width="stretch")

    # Botão de Próximo Passo - Será renderizado no cabeçalho da árvore
    run_next_step = False # Flag para executar lógica


    if solve_clicked:
        try:
            with st.spinner(t("bab.messages.init") if step_by_step else t("bab.messages.solving")):
                # Converter restrições para formato Ax <= b
                A_conv, b_conv = [], []
                for row, rhs, sn in zip(A, b, senses):
                    if sn == "≤":
                        A_conv.append(row)
                        b_conv.append(rhs)
                    elif sn == "≥":
                        A_conv.append([-x for x in row])
                        b_conv.append(-rhs)
                    else:  # igualdade
                        A_conv.append(row)
                        b_conv.append(rhs)
                        A_conv.append([-x for x in row])
                        b_conv.append(-rhs)

                # Adicionar restrições x_i <= 1 para variáveis binárias
                for i in binary_vars:
                    row = [0.0] * n_vars
                    row[i] = 1.0
                    A_conv.append(row)
                    b_conv.append(1.0)

                # Ajustar função objetivo para Minimização se necessário
                final_c = list(c)
                if not is_max:
                    final_c = [-x for x in final_c]

                solver = BranchBoundSolver()
                
                if step_by_step:
                    solver.initialize(final_c, A_conv, b_conv, integer_vars=int_vars, strategy=selected_strategy)
                    st.session_state["bb_solver"] = solver
                    st.rerun() # Força atualização para mostrar o botão de próximo passo imediatamente
                else:
                    # Modo normal (completo)
                    solver.solve(final_c, A_conv, b_conv, integer_vars=int_vars, strategy=selected_strategy)
                    st.session_state["bb_solver"] = solver # Salva para exibir resultados abaixo
                    
        except Exception as e:
            st.error(f"{t('bab.messages.error')} {str(e)}")
            st.exception(e)

    # Lógica de execução do próximo passo (verificação via chave ou botão renderizado posteriormente)
    pass

    # Exibição dos Resultados (sempre que houver um solver no estado)
    if "bb_solver" in st.session_state:
        solver = st.session_state["bb_solver"]
        
        # Resultados Parciais ou Finais
        if solver.nodes: # Só mostrar se já tiver algum nó
            if solver.finished and solver.best_solution is None:
                 st.error(t("bab.messages.no_int_sol"))
                 st.info(t("bab.messages.no_int_bg"))
            else:
                 # Exibir estatísticas (parciais ou finais)
                 best_val_display = f"{solver.best_value:.3f}" if solver.best_value != float("-inf") else "N/A"
                 
                 st.markdown("---") # Adicionado entre botões e números dos resultados
                 col_stats1, col_stats2, col_stats3, col_stats4 = st.columns(4)
                 with col_stats1: st.metric(t("bab.results.best_z"), best_val_display)
                 with col_stats2: st.metric(t("bab.results.nodes_exp"), len(solver.nodes))
                 with col_stats3: st.metric(t("bab.results.nodes_queue"), len(solver.queue))
                 with col_stats4: 
                     integer_nodes = sum(1 for n in solver.nodes if n.get("integer_feasible", False))
                     st.metric(t("bab.results.int_sols"), integer_nodes)

            # Cabeçalho da Árvore + Botão Próximo Passo
            # st.markdown("---") # Removido a pedido do usuário
            col_tree_header, col_tree_btn = st.columns([0.8, 0.2])
            
            with col_tree_header:
                 st.markdown(t("bab.results.tree_title"))
            
            with col_tree_btn:
                 # Se passo a passo ativo e não terminou
                 if step_by_step and not solver.finished:
                      # Alinhar à direita para ficar próximo ao header mas oposto
                      if st.button(t("bab.btn_next"), key="btn_next_step", type="secondary", width="stretch"):
                          run_next_step = True
            
            # Executar lógica do próximo passo se clicado
            if run_next_step:
                 solver.step()
                 st.rerun() # Rerun para atualizar grafo e estatísticas

            # Renderizar Grafo
            _render_branch_bound_tree(solver)
            
            # Exibir logs, solução e legenda ABAIXO do grafo em duas colunas
            st.markdown("---")
            col_results, col_legend = st.columns([0.65, 0.35], gap="large")

            with col_results:
                # Logs Primeiro (Top-Left)
                if solver.steps:
                    with st.expander(t("bab.results.log_title"), expanded=True):
                        for i, step in enumerate(solver.steps):
                             step_text = step
                             if isinstance(step, dict):
                                 step_text = t(step["key"]).format(*step.get("params", []))
                             st.write(f"**{i+1}.** {step_text}")

                # Melhor Solução Inteira (Bottom-Left)
                if solver.best_solution is not None:
                    st.markdown(t("bab.results.best_int_sol"))
                    cols_per_row = min(3, n_vars) # Reduzido para caber na coluna
                    rows_needed = (n_vars + cols_per_row - 1) // cols_per_row
                    solution = solver.best_solution[:n_vars]
                    for row in range(rows_needed):
                        var_cols = st.columns(cols_per_row)
                        for col_idx in range(cols_per_row):
                            var_idx = row * cols_per_row + col_idx
                            if var_idx < n_vars:
                                with var_cols[col_idx]:
                                    val = solution[var_idx]
                                    if abs(val - round(val)) < 1e-6: val_fmt = f"{int(round(val))}"
                                    else: val_fmt = f"{val:.3f}"
                                    st.success(f"**x{var_idx+1} = {val_fmt}**")
            
            with col_legend:
                st.markdown(t("bab.legend"))
                st.info(t("bab.results.legend_info"))
                st.markdown(t("bab.results.legend_items"))

        elif solver.finished: # Sem nós mas finalizado (Erro na Raiz)
             st.error(t("bab.messages.root_error"))
             st.warning(t("bab.messages.root_details"))
             if solver.steps:
                 last_step = solver.steps[-1]
                 step_text = last_step
                 if isinstance(last_step, dict):
                     step_text = t(last_step["key"]).format(*last_step.get("params", []))
                 st.info(f"Log do Solver: {step_text}")


def _format_solution(solution, max_vars_to_show=5):
    import json
    """Formata o array de solução para uma string de dicionário."""
    if solution is None or not isinstance(solution, (list, np.ndarray)):
        return "N/A"
    
    solution_dict = {}
    for i, val in enumerate(solution):
        if i >= max_vars_to_show:
            break
        key = f"X{i+1}"
        solution_dict[key] = f"{float(val):.2f}"

    # Converte o dicionário para uma string formatada
    items = [f"'{k}': {v}" for k, v in solution_dict.items()]
    
    if len(solution) > max_vars_to_show:
        items.append("'...': '...'")
        
    return "{" + ", ".join(items) + "}"


def _render_branch_bound_tree(solver):
    """
    Renderiza a árvore de Branch & Bound usando a biblioteca st-link-analysis.
    """
    
    try:
        from st_link_analysis import st_link_analysis, NodeStyle, EdgeStyle

        nodes_data = []
        edges_data = []

        status_map = {
            "OPTIMAL": {"label": t("bab.tree_labels.OPTIMAL"), "color": "#2e7d32"},
            "INTEGER": {"label": t("bab.tree_labels.INTEGER"), "color": "#8e24aa"},
            "INFEASIBLE": {"label": t("bab.tree_labels.INFEASIBLE"), "color": "#f44336"},
            "PRUNED": {"label": t("bab.tree_labels.PRUNED"), "color": "#9e9e9e"},
            "FRACTIONAL": {"label": t("bab.tree_labels.FRACTIONAL"), "color": "#2196f3"},
            "ROOT": {"label": t("bab.tree_labels.ROOT"), "color": "#ffc107"}
        }

        for node_info in solver.nodes:
            node_id = str(node_info["id"])
            
            status_key = "ROOT"
            if node_info['id'] == 0:
                 status_key = "ROOT"
                 # Se a raiz já for inteira e ótima
                 if node_info.get("integer_feasible") and abs(node_info["value"] - solver.best_value) < 1e-6:
                     status_key = "OPTIMAL"
            elif not node_info["feasible"]:
                status_key = "INFEASIBLE"
            elif node_info.get("integer_feasible"):
                if abs(node_info["value"] - solver.best_value) < 1e-6:
                    status_key = "OPTIMAL"
                else:
                    status_key = "INTEGER"
            elif node_info.get("pruned"):
                status_key = "PRUNED"
            else:
                status_key = "FRACTIONAL"
            
            status_details = status_map[status_key]
            
            bounds_str = ", ".join([f"x{var+1} {op} {val}" for var, (op, val) in node_info.get("bounds", {}).items()])
            
            solution_str = _format_solution(node_info.get("solution"))

            nodes_data.append({
                "data": {
                    "id": node_id,
                    "label": status_details["label"],
                    "caption": f"Z={node_info.get('value', 0):.2f}",
                    "Valor Z": f"{node_info.get('value', 0):.3f}",
                    "Status": status_details["label"],
                    "Bounds": bounds_str if bounds_str else "Nenhum",
                    "Solução": solution_str
                }
            })

            if node_info.get("parent") is not None:
                branch_label = node_info.get("branch_reason", "BRANCH")
                edges_data.append({
                    "data": {
                        "id": f'edge_{node_info["parent"]}_{node_id}',
                        "label": branch_label,
                        "source": str(node_info["parent"]),
                        "target": node_id,
                        "Solução": solution_str  # Adds solution info to the edge sidebar
                    }
                })
        
        node_styles = [
            NodeStyle(status["label"], status["color"], "caption")
            for status in status_map.values()
        ]

        # Gerar estilos de aresta dinamicamente para cada label única
        unique_edge_labels = set(e["data"]["label"] for e in edges_data)
        edge_styles = [
            EdgeStyle(label, color="#888888", directed=True, caption=label)
            for label in unique_edge_labels
        ]

        # Ajuste de Layout para evitar sobreposição
        layout_config = {
            "name": "dagre",
            "rankDir": "TB",      # Direção: Top-to-Bottom
            "rankSep": 50,        # Ajustado para equilíbrio
            "nodeSep": 40,        # Ajustado para equilíbrio
            "spacingFactor": 1.2,
        }

        st_link_analysis(
            elements={"nodes": nodes_data, "edges": edges_data},
            layout=layout_config,
            node_styles=node_styles,
            edge_styles=edge_styles,
            key=f"bb_tree_viz_{len(solver.nodes)}" # Chave dinâmica para forçar re-renderização do layout a cada passo
        )
        
    except Exception as e:
        st.error(f"❌ Ocorreu um erro inesperado ao tentar renderizar a árvore: {str(e)}")
        st.exception(e)