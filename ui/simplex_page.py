from typing import List

import streamlit as st

from .helpers import _store_problem, _load_problem, number_emojis
from core.simplex_solver import SimplexSolver
from .plots import feasible_region_2d, feasible_region_3d
from .tableau_display import (
    show_tableau_with_basis_info, 
    show_final_solution,
    show_optimization_summary,
    extract_basis_variables
)

from ui.lang import t

def simplex_ui():
    st.markdown(f"<h1 style='text-align: center;'>{t('simplex.title')}</h1>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # carregamento de estado anterior (se existir)
    saved = st.session_state.get("problem", {})
    sv_c, sv_A, sv_b = saved.get("c", []), saved.get("A", []), saved.get("b", [])

    col_counts = st.columns(3)
    with col_counts[0]:
        n_vars = st.number_input(t("simplex.n_vars"), 2, 10, max(len(sv_c), 2), help=t("simplex.vars_help"))
    with col_counts[1]:
        n_cons = st.number_input(t("simplex.n_cons"), 1, 10, max(len(sv_A), 1), help=t("simplex.cons_help"))

    # Ler preferência de maximização salva
    saved_maximize = saved.get("maximize", True)
    maximize_idx = 0 if saved_maximize else 1

    with col_counts[2]:

        maximize = st.selectbox(
            t("simplex.obj_type"),
            (t("simplex.maximize"), t("simplex.minimize")),
            index=maximize_idx,
            help=t("simplex.obj_help")
        )
        
    is_max = (maximize == t("simplex.maximize"))

    st.markdown(f"#### {t('simplex.obj_func')}", help=t("simplex.obj_help"))
    
    # Variable type options
    type_options = [t("simplex.var_real"), t("simplex.var_integer"), t("simplex.var_binary")]
    
    obj_cols = st.columns(n_vars)
    c: List[float] = []
    var_types: List[str] = []
    for i in range(n_vars):
        default = sv_c[i] if i < len(sv_c) else 1.0
        with obj_cols[i]:
            # Type selector (Travado em Real para Simplex)
            vtype = st.selectbox(
                f"{t('simplex.var_type')} x{i+1}",
                type_options,
                index=0,
                key=f"vtype_{i}",
                label_visibility="collapsed",
                disabled=True
            )
            var_types.append(vtype)
            
            # Sempre real no Simplex
            val = st.number_input(f"**x{i+1}**", value=float(default), key=f"c_{i}", help=f"{t('simplex.coef_help')} x{i+1}")
            c.append(val)

    # ---------- restrições -------------------------------------------
    # ---------- restrições -------------------------------------------
    with st.expander(t("simplex.constraints"), expanded=True):
        
        A: List[List[float]] = []
        b: List[float] = []
        senses: List[str] = []
        
        for r in range(n_cons):
            st.markdown(f"**{t('common.restriction')} - {number_emojis[r+1]}:**")
            cols = st.columns(n_vars + 2)  # variáveis + seletor + RHS
            row = []
            
            # Inputs dos coeficientes das variáveis
            for i in range(n_vars):
                default = sv_A[r][i] if r < len(sv_A) and i < len(sv_A[r]) else 1.0
                with cols[i]:
                    row.append(st.number_input(
                        f"**x{i+1}**", 
                        value=default, 
                        key=f"a_{r}_{i}",
                        help=f"{t('simplex.coef_help')} x{i+1}"
                    ))
            
            # Seletor do tipo de restrição
            with cols[n_vars]:
                sense = st.selectbox(
                    t("simplex.type_label"), 
                    ["≤", "=", "≥"], 
                    index=0, 
                    key=f"sense_{r}",
                    help=t("simplex.type_label")
                )
            
            # Valor do lado direito (RHS)
            with cols[n_vars + 1]:
                rhs_default = sv_b[r] if r < len(sv_b) else 1.0
                rhs = st.number_input(
                    t("simplex.rhs_label"), 
                    value=rhs_default, 
                    key=f"rhs_{r}",
                    help=t("simplex.rhs_label")
                )
            
            A.append(row)
            b.append(rhs)
            senses.append(sense)

    # -------- botão resolver ----------------------------------------
    col_opt1, col_opt2, col_btn = st.columns([0.35, 0.25, 0.4])
    with col_opt1:
        didactic_mode = st.checkbox(t("simplex.didactic"), value=True, help="Mostrar explicações detalhadas passo a passo", key="didactic_mode_cb")
    with col_opt2:
        step_by_step = st.checkbox(t("simplex.step_by_step"), value=False, disabled=not didactic_mode)
        if not didactic_mode: step_by_step = False
    with col_btn:
        solve_clicked = st.button(t("simplex.btn_solve"), type="primary", width="stretch")

    if solve_clicked:
        # Derive int_vars from var_types
        int_vars = []
        binary_vars = []
        for i, vt in enumerate(var_types):
            if vt == t("simplex.var_integer"):
                int_vars.append(i)
            elif vt == t("simplex.var_binary"):
                int_vars.append(i)
                binary_vars.append(i)
        
        # If there are integer/binary vars, redirect to B&B
        if int_vars:
            # Add binary upper-bound constraints (x_i <= 1) for binary vars
            A_for_bb = [row[:] for row in A]
            b_for_bb = list(b)
            for bi in binary_vars:
                bound_row = [0.0] * n_vars
                bound_row[bi] = 1.0
                A_for_bb.append(bound_row)
                b_for_bb.append(1.0)
            
            # Store problem for B&B page
            st.session_state["problem"] = {
                "c": c,
                "A": A_for_bb,
                "b": b_for_bb,
                "maximize": is_max,
                "int_vars": int_vars,
                "var_types": [("real" if vt == t("simplex.var_real") else "integer" if vt == t("simplex.var_integer") else "binary") for vt in var_types]
            }
            st.session_state["pending_toast"] = t("simplex.auto_bab_info")
            st.session_state["pending_redirect"] = "bab"
            st.rerun()
            return
        
        # Pré-processar sentidos: converter tudo para ≤
        A_conv, b_conv = [], []
        for row, rhs, sn in zip(A, b, senses):
            if sn == "≤":
                A_conv.append(row)
                b_conv.append(rhs)
            elif sn == "≥":
                A_conv.append([-x for x in row])
                b_conv.append(-rhs)
            else:  # igualdade → duas
                A_conv.append(row)
                b_conv.append(rhs)
                A_conv.append([-x for x in row])
                b_conv.append(-rhs)
        
        try:
             solver = SimplexSolver()
             # is_max já está definido na linha 41
             
             if step_by_step and didactic_mode:
                 solver.initialize(c, A_conv, b_conv, maximize=is_max)
                 st.session_state["simplex_solver"] = solver
                 st.session_state["simplex_params"] = {
                     "c": c, "A": A_conv, "b": b_conv, "max": is_max
                 }
                 st.rerun()
             else:
                 solver.solve(c, A_conv, b_conv, maximize=is_max)
                 st.session_state["simplex_solver"] = solver
                 st.session_state["simplex_params"] = {
                     "c": c, "A": A_conv, "b": b_conv, "max": is_max
                 }
                 
                 # Salvar histórico no modo normal
                 if solver.optimal:
                     sol, z = solver.get_solution()
                     st.session_state.setdefault("history", []).append({
                        "method": "Simplex", "c": c, "A": A, "b": b, "z": z, "solution": sol, "maximize": is_max
                     })
                     
        except Exception as e:
             st.error(f"Erro ao iniciar solver: {e}")
             st.exception(e)



    # --------------------------------------------------------------------------
    # Renderização de Resultados
    # --------------------------------------------------------------------------
    if "simplex_solver" in st.session_state:
        solver = st.session_state["simplex_solver"]
        params = st.session_state.get("simplex_params", {})
        is_max = params.get("max", True)
        
        if solver.unbounded:
            st.error(t("simplex.results.unbounded"))
        elif solver.infeasible:
             st.error(t("simplex.results.infeasible"))
        
        # Validar se tem tableaux para mostrar
        if solver.tableaux:
             # Tenta extrair solução se ótima
             if solver.optimal:
                 try:
                     final_sol, final_z = solver.get_solution()
                     st.success(t("simplex.results.optimal_found"))
                     basis_info = solver.get_basis_info()
                     show_final_solution(
                        solution=final_sol, 
                        objective_value=final_z, 
                        basis_info=basis_info,
                        maximize=is_max,
                        method="Simplex Primal",
                        iterations=len(solver.steps) - 1
                     )
                 except Exception as e:
                     st.warning(f"Detalhes da solução não disponíveis: {e}")

             # ----- Mostrar iterações do algoritmo ------------------------
             st.markdown("---")
             col_hdr, col_nx = st.columns([0.75, 0.25])
             with col_hdr:
                 st.markdown(t("simplex.results.iterations_title"))
             with col_nx:
                 if step_by_step and didactic_mode and not solver.finished:
                     if st.button(t("simplex.results.next_step"), type="primary", key="btn_next_step_simplex_inline"):
                         solver.step()
                         st.rerun()
                
        for idx, (tbl, step, desc, piv) in enumerate(
            zip(solver.tableaux, solver.steps, solver.decisions, solver.pivots)
        ):
            # Expandir lógica
            is_initial = idx == 0
            is_final = "Ótima" in step or "Optimal" in step
            is_last = idx == len(solver.tableaux) - 1
            
            # Tratamento de Logs Internacionalizados
            step_text = step
            if isinstance(step, dict):
                step_text = t(step["key"]).format(*step.get("params", []))
            
            desc_text = desc
            if isinstance(desc, dict):
                desc_text = t(desc["key"]).format(*desc.get("params", []))

            # Verificar se é passo final visualizando o texto traduzido ou a chave
            is_initial = idx == 0
            is_final = False
            if isinstance(step, dict):
                is_final = "optimal" in step["key"]
            else:
                 is_final = "Ótima" in step_text or "Optimal" in step_text
            
            is_last = idx == len(solver.tableaux) - 1
            
            # Se passo a passo, expande apenas o último. Se não, expande inicial e final.
            should_expand = is_last if step_by_step else (is_initial or is_final)
            
            if didactic_mode:
                with st.expander(f"**{step_text}**", expanded=should_expand):
                    st.markdown(desc_text)
                    st.markdown("---")
                    
                    # Extrair informações da base para este tableau
                    if hasattr(solver, '_current_basis') and idx > 0:
                        basis_info = extract_basis_variables(tbl, solver._current_basis, len(c))
                    else:
                        basis_info = [(f"s{i+1}", tbl[i+1, -1]) for i in range(tbl.shape[0]-1)]
                    # Mostrar tableau com índices corretos das variáveis básicas
                    show_tableau_with_basis_info(tbl, basis_info, pivot=piv, show_legend=didactic_mode)
                    
                    if piv != (-1, -1) and idx > 0:
                        pr, pc = piv
                        st.markdown("---")
                        st.markdown(t("simplex.results.pivot_summary"))
                        col1, col2, col3 = st.columns(3)
                        with col1: st.success(f"{t('simplex.results.enters_basis')}\n\nx{pc+1}")
                        with col2: st.warning(f"{t('simplex.results.pivot_element')}\n\n{tbl[pr, pc]:.3f}")
                        with col3: st.error(f"{t('simplex.results.leaves_basis')}\n\nLinha {pr}")
                        
                        st.markdown(t("simplex.results.tech_details"))
                        details_col1, details_col2 = st.columns(2)
                        with details_col1:
                            pivot_pos_labels = [
                                t("simplex.results.details.line").format(pr),
                                t("simplex.results.details.col").format(pc+1),
                                t("simplex.results.details.val").format(tbl[pr, pc])
                            ]
                            st.markdown(f"{t('simplex.results.pivot_pos')}\n" + "\n".join(pivot_pos_labels))
                        with details_col2:
                            ops_labels = [
                                t("simplex.results.details.op_div").format(pr, tbl[pr, pc]),
                                t("simplex.results.details.op_elim").format(pc+1),
                                t("simplex.results.details.op_update")
                            ]
                            st.markdown(f"{t('simplex.results.ops_performed')}\n" + "\n".join(ops_labels))

                    if idx > 0:
                        st.markdown("---")
                        st.markdown(t("simplex.results.basis_analysis"))
                        basic_vars = [info for info in basis_info if abs(info[1]) > 1e-6]
                        if basic_vars:
                            st.markdown(t("simplex.results.interpretation"))
                            decision_vars = [(name, val) for name, val in basic_vars if name.startswith('x')]
                            slack_vars = [(name, val) for name, val in basic_vars if name.startswith('s')]
                            if decision_vars: st.markdown(f"{t('simplex.results.active_vars')} {', '.join([f'{n} = {v:.3f}' for n, v in decision_vars])}")
                            if slack_vars: st.markdown(f"{t('simplex.results.slack_vars')} {', '.join([f'{n} = {v:.3f}' for n, v in slack_vars])}")
                            all_decision_vars = [f"x{i+1}" for i in range(len(c))]
                            basic_decision_names = [name for name, _ in decision_vars]
                            non_basic_decision = [var for var in all_decision_vars if var not in basic_decision_names]
                            if non_basic_decision: st.markdown(f"{t('simplex.results.non_basic')} {', '.join(non_basic_decision)}")

            else:
                # Modo Não-Didático: Apenas Tableau Limpo
                
                st.markdown(f"##### **{step_text}**")
                # Passar basis_vars=None para esconder a seção "Status da Base Atual"
                show_tableau_with_basis_info(tbl, basis_vars=None, pivot=piv, show_legend=False)
                st.markdown("---")

        # ----- Visualização da Região Factível (2D/3D) -------------------
        if params.get("A") and params.get("b"):
             A_plot = params["A"]
             b_plot = params["b"]
             c_plot = params["c"]
             n_plot = len(c_plot)
             
             optimal_sol = None
             if solver.optimal:
                 try:
                     sol_values, _ = solver.get_solution()
                     # Garantir que temos valores para as variáveis originais
                     if len(sol_values) >= n_plot:
                        optimal_sol = sol_values[:n_plot]
                 except:
                     pass

             fig = None
             if n_plot == 2:
                 st.markdown(t("simplex.results.plot_2d"))
                 fig = feasible_region_2d(c_plot, A_plot, b_plot, optimal_solution=optimal_sol)
             elif n_plot == 3:
                 st.markdown(t("simplex.results.plot_3d"))
                 fig = feasible_region_3d(c_plot, A_plot, b_plot, optimal_solution=optimal_sol)
             
             if fig:
                 st.plotly_chart(fig, use_container_width=True)
             elif n_plot in [2, 3]:
                 # Se não gerou figura mas é 2D/3D, avisa.
                 pass
                



