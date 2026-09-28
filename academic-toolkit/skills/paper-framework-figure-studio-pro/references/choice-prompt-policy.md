# Choice Prompt Policy v3.2.13

S0-S4 responses may provide exactly one next legal copyable prompt when the next public step has not been executed.

S5 is terminal. After S5 image generation, do not offer a next workflow prompt, selection stage, caption stage, audit stage, or revision loop. If asked what remains, answer exactly:

```text
我的任务已经完成，剩下由人类来决策。
```
