# P01 基线产出 (baseline)

- 子问题：①候选中心选址(0-1) ②需求-中心分配 ③总成本=建仓+运营+运输
- 变量：x_j∈{0,1} 候选j是否建仓；y_ij∈[0,1] 需求i由中心j服务比例
- 目标：min Σ_j F_j x_j + Σ_j c_j·(Σ_i d_i y_ij) + Σ_ij t_ij d_i y_ij
- 约束：Σ_j y_ij=1 ∀i；y_ij ≤ x_j；cap_j·x_j ≥ Σ_i d_i y_ij
- 算法：Gurobi/OR-Tools MIP，或贪心+局部搜索启发式
