# P02 基线

- dS/dt=-beta*S*I/N; dI/dt=beta*S*I/N - gamma*I; dR/dt=gamma*I
- 干预：beta'=beta*0.5 (隔离7天)
- 数值：Euler/RK4，dt=0.1，T=60
- 指标：Imax=max(I), t_peak=argmax, R_end=R(T)
