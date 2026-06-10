
from __future__ import annotations

import math
from copy import deepcopy
from typing import Dict, List

from .simplex_solver import SimplexSolver


class BranchBoundSolver:
    """Branch‑and‑Bound usando Simplex como relaxação linear.

    *Compatível com Python ≥ 3.7 (removido o uso do operador walrus).*"""

    def __init__(self) -> None:
        self.nodes: List[Dict] = []
        self.best_solution: List[float] | None = None
        self.best_value: float = float("-inf")
        self.steps: List[str] = []

    # ------------------------------------------------------------------ PUBLIC API
    # ------------------------------------------------------------------ PUBLIC API
    def initialize(
        self,
        c: List[float],
        A: List[List[float]],
        b: List[float],
        integer_vars: List[int] | None = None,
        node_limit: int = 100,
        strategy: str = "BFS",
    ) -> None:
        """Inicializa o solver para execução passo a passo."""
        # Reset state ---------------------------------------------------
        self.nodes.clear()
        self.steps.clear()
        self.best_solution = None
        self.best_value = float("-inf")
        
        # Store problem data
        self.c = c
        self.A = A
        self.b = b
        self.integer_vars = integer_vars if integer_vars is not None else list(range(len(c)))
        self.node_limit = node_limit
        self.strategy = strategy
        
        # Internal state
        self.queue: List[int] = []
        self.next_id = 1
        self.finished = False

        # ----------------------------------------------------------- Raiz
        root_simplex = SimplexSolver()
        root_simplex.solve(self.c, self.A, self.b, maximize=True)
        if not root_simplex.optimal or root_simplex.unbounded:
            self.steps.append({
                "key": "bab.log.relaxed_infeasible",
                "params": []
            })
            self.finished = True
            return

        root_sol, root_val = root_simplex.get_solution()
        root_node = self._add_node(
            node_id=0,
            parent=None,
            bounds={},
            sol=root_sol,
            val=root_val,
            int_vars=self.integer_vars,
        )
        if self._is_int(root_sol, self.integer_vars):
            self.best_solution, self.best_value = root_node["solution"], root_val
            self.steps.append({
                "key": "bab.log.integer_root",
                "params": []
            })
            self.finished = True
            return

        self.queue.append(0)

    def step(self) -> bool:
        """Executa um passo (processa um nó). Retorna True se continuar, False se terminou."""
        if self.finished:
            return False
            
        if not self.queue or self.next_id >= self.node_limit:
            self.finished = True
            return False

        # Seleção do nó baseado na estratégia
        if self.strategy == "BestBound":
            self.queue.sort(key=lambda nid: self.nodes[nid]["value"], reverse=True)
            current_id = self.queue.pop(0)
        elif self.strategy == "DFS":
            current_id = self.queue.pop() # LIFO
        else: # BFS (default)
            current_id = self.queue.pop(0) # FIFO

        node = self.nodes[current_id]
        
        # poda por processamento ou bound
        if node["processed"] or node["value"] <= self.best_value:
            # Se podado, apenas retornamos True para tentar o próximo na próxima chamada
            # Mas marcamos como processado se não estava
            node["processed"] = True
            node["pruned"] = True
            return True
            
        node["processed"] = True

        frac_idx = self._first_frac(node["solution"], self.integer_vars)
        if frac_idx == -1: 
            return True

        x_val = node["solution"][frac_idx]
        self.steps.append({
            "key": "bab.log.branch",
            "params": [frac_idx+1, x_val]
        })

        for op, bound in (("<=", math.floor(x_val)), (">=", math.ceil(x_val))):
            new_bounds = deepcopy(node["bounds"])
            new_bounds[frac_idx] = (op, bound)

            sub_A, sub_b = self._apply_bounds(self.A, self.b, new_bounds)
            relax = SimplexSolver()
            relax.solve(self.c, sub_A, sub_b, maximize=True)

            if not relax.optimal or relax.unbounded:
                self.steps.append({
                    "key": "bab.log.sub_infeasible",
                    "params": [frac_idx+1, op, bound]
                })
                self._add_node(
                    node_id=self.next_id,
                    parent=current_id,
                    bounds=new_bounds,
                    sol=None,
                    val=float("-inf"),
                    feasible=False,
                    int_vars=self.integer_vars,
                    branch_reason=f"x{frac_idx+1} {op} {bound:.0f}"
                )
                self.next_id += 1
                continue

            sub_sol, sub_val = relax.get_solution()
            new_node = self._add_node(
                node_id=self.next_id,
                parent=current_id,
                bounds=new_bounds,
                sol=sub_sol,
                val=sub_val,
                int_vars=self.integer_vars,
                branch_reason=f"x{frac_idx+1} {op} {bound:.0f}"
            )

            # actualização da melhor solução inteira
            if new_node["integer_feasible"] and sub_val > self.best_value:
                self.best_solution, self.best_value = new_node["solution"], sub_val
                self.steps.append({
                    "key": "bab.log.update_best",
                    "params": [sub_val]
                })
            # Enfileira nós fracionários promissores
            elif not new_node["integer_feasible"] and sub_val > self.best_value:
                self.queue.append(self.next_id)
            else:
                # Nó não é inteiro e bound <= best_value → podado por qualidade
                new_node["pruned"] = True

            self.next_id += 1
            
        return True

    def solve(
        self,
        c: List[float],
        A: List[List[float]],
        b: List[float],
        integer_vars: List[int] | None = None,
        node_limit: int = 100,
        strategy: str = "BFS",
    ) -> None:
        """Resolve o PLI por Branch & Bound."""
        self.initialize(c, A, b, integer_vars, node_limit, strategy)
        while self.step():
            pass

    # ------------------------------------------------------------------ helpers
    def _add_node(
        self,
        node_id: int,
        parent: int | None,
        bounds: Dict[int, tuple[str, float]],
        sol: List[float] | None,
        val: float,
        int_vars: List[int] | None = None,
        feasible: bool = True,
        branch_reason: str | None = None,
    ) -> Dict:
        """Cria e armazena um nó na lista self.nodes."""
        if int_vars is None:
            int_vars = []

        int_feasible = sol is not None and self._is_int(sol, int_vars)
        
        clean_sol = None
        if sol is not None:
            clean_sol = list(sol)
            for i in int_vars:
                if i < len(clean_sol) and abs(clean_sol[i] - round(clean_sol[i])) < 1e-6:
                    clean_sol[i] = float(round(clean_sol[i]))

        node = {
            "id": node_id,
            "parent": parent,
            "bounds": bounds,
            "solution": clean_sol,
            "value": val,
            "feasible": feasible,
            "integer_feasible": int_feasible,
            "processed": False,
            "branch_reason": branch_reason,
        }
        self.nodes.append(node)
        return node

    @staticmethod
    def _is_int(sol: List[float], ivars: List[int]) -> bool:
        """Checa se *todas* variáveis em *ivars* são inteiras em *sol*."""
        return all(abs(sol[i] - round(sol[i])) < 1e-6 for i in ivars)

    @staticmethod
    def _first_frac(sol: List[float], ivars: List[int]) -> int:
        """Retorna índice da primeira variável fracionária ou −1 se nenhuma."""
        for i in ivars:
            if abs(sol[i] - round(sol[i])) > 1e-6:
                return i
        return -1

    # ---------- util para adicionar bounds extra ao problema original ----
    @staticmethod
    def _apply_bounds(
        A: List[List[float]],
        b: List[float],
        bounds: Dict[int, tuple[str, float]],
    ) -> tuple[List[List[float]], List[float]]:
        new_A, new_b = deepcopy(A), deepcopy(b)
        n = len(A[0])
        for var_idx, (op, val) in bounds.items():
            row = [0.0] * n
            if op == "<=":
                row[var_idx] = 1.0
                rhs = val
            else:  # ">=" → -x ≤ -val
                row[var_idx] = -1.0
                rhs = -val
            new_A.append(row)
            new_b.append(rhs)
        return new_A, new_b