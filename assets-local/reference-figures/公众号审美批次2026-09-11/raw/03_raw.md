> 原始抓取件：firecrawl_scrape 2026-09-11，URL https://mp.weixin.qq.com/s/YuKh_Xpnu2w4dea06ZgTrA

# 巧用渐变色，打造更有质感的图形

R语言数据分析指南
Jul 25, 2026, 9:03 AM

> 历时打磨，我们编写的《R语言学术图表绘制：用ggplot2绘制顶级期刊图表》终于正式出版了。本节来展示书中的渐变色相关的图，书中的案例均提供数据 + 代码供读者下载，可直接运行复现。全彩印刷，各大平台均有销售。

渐变色通过颜色的平滑过渡，不仅增强了图形的层次感与视觉美感，也有助于更直观地表达数值分布与趋势变化。

### 渐变色箱线图

该图主要展示了如何在图形内部设置渐变色背景

![Image](https://mmbiz.qpic.cn/sz_mmbiz_png/4uxvYT883odM1SLRpFR4PSpuc4WQYRhIibujDb7XErqBqEPHTicUeupic0f40iaTEgEI1wn1cWN9ONjbYGWCU2H6eibBb5LmaRuqiaiaRiawzqbnMs0/640?wx_fmt=png&from=appmsg#imgIndex=0)

![Image](https://mmbiz.qpic.cn/mmbiz_png/4uxvYT883ofYp7RhCibVSdd0mnMl0MG3WzToptwFsD0NntUwTRHFfDE9pNHRt1AsMHMnyich8YGeukQOu1Nzn2c1xdmSSSWWIUXVdELwNAnoM/640?wx_fmt=png&from=appmsg#imgIndex=1)

### 渐变色分背景条带

该图则演示了如何为轴标签区域添加渐变色背景，从而实现更具层次感和引导性的视觉效果。

![粘贴图片](https://mmbiz.qpic.cn/mmbiz_png/4uxvYT883odg6QVWM8Yb8JR1p4AHkH85ItwkGibNIibblxmsKQOWI81bJZTxxH17q5QTeEIVzVkXOicZl8Ct6qByyH2yicm44VEzD2eaz52dDqY/640?wx_fmt=png&from=appmsg#imgIndex=2)此图仅为在标准散点图的基础上，对 y 轴区域添加渐变色背景。由于渐变色位于图形外部，为确保其可见，需通过 coord_cartesian(clip = "off") 关闭坐标裁剪。代码中主要使用 legendry 包来实现分组文本的添加，使用前请安装此包。

### 渐变色维恩图

![粘贴图片](https://mmbiz.qpic.cn/mmbiz_png/4uxvYT883oe9jiaNwqSuXsNB2S25tgaVyuW7rz2bF3effP4OK8JLQ9mzE8Oh7LJgNylicB4zmLxdic1ibPZtN6qPn8WqTbJvTDIa2WZeSnoTegg/640?wx_fmt=png&from=appmsg#imgIndex=3)

![Image](https://mmbiz.qpic.cn/mmbiz_png/4uxvYT883ocvbHTZTG2OhxTg9NiahDib1T42xHeicMpriakv2rnQvibXTXzmQAId3PRFY2LG7icic16uopUxxQKpUCfnYNwOJZGd7sV67qoBRCwAHA/640?wx_fmt=png&from=appmsg#imgIndex=4)

### 渐变色桑基图

基础桑基图通常使用静态颜色区分数据流。为了增加视觉吸引力和层次感，可以引入渐变色设计。在基础桑基图上，渐变色不仅反映数据流向，还通过色彩变化展示数据的强度和流动过程。

![粘贴图片](https://mmbiz.qpic.cn/mmbiz_png/4uxvYT883ocXUyaMeKXroUpiazv3boHJM7rc8glGcq8ricHeiaYeSLu47sWc4WicVUInZpziaVCkNJbVrOfY7UDicbkxMwQwicdnJdd2M0bgjiaeiaLw/640?wx_fmt=png&from=appmsg#imgIndex=5)

本书最大的特点之一是体系化。前面的基础知识、数据处理、图形语法和美学映射等内容，为后续案例奠定了基础；而后面的每一个绘图案例，又都能与前面讲解的知识点形成呼应。这种由基础到进阶、由原理到实战的结构设计，使整本书具有很强的连续性和学习价值。同时，读者也无需过分担心版本差异，ggplot2 具有良好的兼容性，大多数示例代码在新版本环境下也可直接运行，相关 R 包保持正常更新即可。

（注：文末为图书京东购买卡片与公众号推广，属商业物料，未收录。）
