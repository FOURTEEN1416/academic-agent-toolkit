# Codex让我的科研绘图提升好几个档次，这个skill神助攻了

- 公众号：AIPaperWrite AI论文写作（作者 Anan0729）
- 发布时间：2026-09-01
- 原文链接：https://mp.weixin.qq.com/s/HgyVcMlO2X4jONU6UsEE9w
- 抓取日期：2026-09-11（firecrawl，图片已本地化）

配图 9 张（去重后），下载成功 9，失败 0。

---

# Codex让我的科研绘图提升好几个档次，这个skill神助攻了

Original Anan0729 Anan0729
AIPaperWrite AI论文写作
Sep 1, 2026, 11:52 AM

![Image](https://mmbiz.qpic.cn/mmbiz_png/UMphHEBOGsNNj75pNG6OpjxeqOcwHnPdlAroXohTTVzQzApWb0zmfsxVCFAFicryoag5xdvKJkqfUcAqyyD9liarZ4TD0pnVRPbhBSzrZUzW0/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=0)

科研绘图最耗时间的地方，经常发生在图已经画出来以后。

坐标轴挤在一起颜色投影以后分不清，图例挡住数据导出的 PNG 一放大就会很模糊。想改成SVG又发现文字全变成路径。这些小麻烦每一项都不难解决，但是凑在一张图里就很磨人，多少宝子们被折磨过。。。

小编这次把 **Scientific Visualization Book**里的四段公开代码交给Codex，再让 `scientific-visualization` Skill 负责整理。最后得到四组PNG和可编辑SVG，另外保留了生成参数、随机种子与导出记录。

![本次生成的四组结果。它们来自原书的 BSD 代码结构，经过重新排版和适配，没有复制原书成品图片。](https://mmbiz.qpic.cn/mmbiz_png/UMphHEBOGsOGaicH2WtXFK2WelWUEXf2q5jdD8XVRMKNdpmHEiahm416gIibONGYu7nG4CpLMNc4N1Ez46zDiaze2FHfOg2ibX7A2Ja8weBdKOdI/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=1)本次生成的四组结果

## 一、这个 Skill 管的事情很具体

`scientific-visualization` 来自K-Dense的 Scientific Agent Skills。它不会凭空知道你的实验结论，也不会替你决定哪组结果更重要。它给 Codex 补上的是一套科研绘图规矩。

图里的数值从哪里来，缺失值怎样处理，做过哪些筛选和变换，都要留下记录。柱形和面积图通常要看零基线，颜色不能承担全部区分任务。导出后还要检查尺寸、背景、文字和矢量文件，不能只看绘图窗口里是否漂亮。

这套 Skill 还带了样式、配色检查和导出工具。此次四个样例都实际调用了它的 `style_context` 和 `figure_export`，每张图同时生成 PNG 与 SVG，并写入来源说明。

如果只安装这一项，可以把下面这段交给 Codex。

> 帮我安装 K-Dense-AI/scientific-agent-skills 里的 scientific-visualization，只安装这一项。先检查目录，不要覆盖已有 Skill。安装完成后告诉我放到了哪里，以及需要重新打开会话吗。

项目名称Scientific Agent Skills。昨天的分享里有。

## 二、我怎样让它复刻书里的图

《Scientific Visualization》由Nicolas P. Rougier编写，围绕Python和 Matplotlib 讲解坐标、尺度、配色、排版与高级图形。项目公开了全书代码。书稿与代码的许可证不同，本文只使用其中采用BSD许可证的代码，并保留作者和来源说明。

我没有让Codex照着截图猜。截图只能告诉它大概长什么样，无法交代数据和变换。更稳的做法是给出原始脚本、目标用途和不能改动的内容。

这次使用的总提示词如下。

> 请使用 scientific-visualization 处理这四段绘图代码。保留原脚本的数学关系和核心构图，修掉本机缺少字体或 LaTeX 时的依赖问题。每张图都要适合公众号手机阅读，标明数据属于计算结果还是合成演示。不要添加不存在的统计结论。分别导出清晰 PNG 和文字可编辑的 SVG，保留随机种子、参数、原代码路径和修改记录。最后检查字号、遮挡、背景和图片尺寸。

下面四个例子使用同一套要求，具体处理各不相同。为了能复现，我把实际送进绘图代码的数据另存为CSV。下面同时写出数据生成方式、原书代码和逐图提示词。

## 三、样例①-多频率振荡曲线

第一张参考原书 `code/colors/colored-plot.py`。原代码把多组振荡曲线叠在黑色背景上，并让颜色沿曲线变化，视觉冲击很强。

用于科研稿件时，我更希望读者能分清每条曲线。此次保留振荡关系，改用明确的离散配色和线型，补上时间与归一化振幅。读者即使看灰度打印，也能靠线型继续辨认。

### 数据怎么来的

这张图没有外部实验数据。时间从0到12秒，共900个点。四条曲线都按 `x(t)=exp(-d·t)·sin(ω·t+φ)` 计算，角频率分别为0.8、1.1、1.4和1.8 rad/s，阻尼系数为0.06、0.075、0.09和0.105，相位依次为0、0.25、0.50和0.75 rad。原书结构来自这段代码github上也可以找到。

![Image](https://mmbiz.qpic.cn/mmbiz_png/UMphHEBOGsMW0mawjne75k58RdKfjem01Q1reXqTmSjG9ZzKtRzguhKFhVhv3aYiaQGSibHpiasXfQrQyQj4090icyP7YlAHTQ99WKcO6gH0zIk/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=2)

### 提示词：

> 使用 scientific-visualization 参考 colored-plot.py 重画多频率振荡曲线。时间范围0到12秒，取900个点。使用公式 x(t)=exp(-d·t)·sin(ω·t+φ)，频率和阻尼按我提供的四组参数计算。保留全部数值，不做平滑。颜色使用色觉友好方案，再用不同线型重复区分。坐标轴写清时间、归一化振幅和单位，导出PNG、可编辑SVG、数据CSV及来源记录。

![根据确定性公式计算的演示曲线。颜色与线型同时编码频率，没有实验观测或统计推断。](https://mmbiz.qpic.cn/sz_mmbiz_png/UMphHEBOGsMzmicdj6NDqKFFRTvDVbHmetGuDNLOR0Jib5IbS5M1mWgiasc4PJc5hJI6PhyemJU3YgjGVg9ggsZicLuhRcn8kVMNlNMCPam4yWw/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=3)根据确定性公式计算的演示曲线。

## 四、样例②-带边缘分布的散点图

第二张参考 `code/ornaments/elegant-scatter.py`。原书脚本生成两组身高、体重和年龄的合成数据，并在坐标轴边缘画出短线，让横向和纵向分布更容易观察。

这次仍然使用固定随机种子的合成数据。组别同时用颜色和点形状区分，年龄用点大小表示，边缘短线保留。图注直接写明是合成演示，避免读者把它当成真实人群研究。

### 数据怎么来的

这也没有外部人群数据。随机种子固定为1，每组250条。A组身高取均值1.60米、标准差0.10米，体重取均值50公斤、标准差10公斤；B组对应参数为1.75米、0.10米、75公斤和10公斤。年龄在25至50岁之间均匀生成，只用来控制点大小。原书代码是 elegant-scatter.py。

![Image](https://mmbiz.qpic.cn/sz_mmbiz_png/UMphHEBOGsPvaZ8MY4vGictnCSz9iagVj7PVYReACRb2tLWLnjeyXRicroPw2FTKgkZrdBbLssRcfWogic81A3cKtq5x1zX4MsAngCicJhuHTpC0/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=4)

### 提示词

> 使用 scientific-visualization 参考 elegant-scatter.py 生成一张带边缘分布的散点图。明确写成固定随机种子的合成演示。两组各250条，按我提供的正态分布参数生成身高和体重，年龄在25至50岁之间生成。组别同时用颜色和点形状区分，年龄映射到点大小，坐标轴边缘保留分布短线。不要添加显著性、相关系数或人群结论。导出PNG、可编辑SVG、500行CSV与参数记录。

![合成数据演示。颜色和点形状表示组别，点大小表示25至50岁的合成年龄，边缘短线展示两个变量的分布位置。](https://mmbiz.qpic.cn/mmbiz_png/UMphHEBOGsNkXQ0UaluncX2ibuVLjHNjO6Vt2ejibuoh94ju7UsBql0OuugVV0hemhTM5OMGaeTfBicJ1icCHbqlicyspAqSuRmSdViaiaE981SqxQ/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=5)合成数据演示

一张散点图塞进三个变量以后，很容易乱。Skill 没有为了好看再增加第四种编码，也没有把随机生成的差异写成研究发现。

## 五、样例③-贝塞尔函数与零点

第三张参考 `code/ornaments/bessel-functions.py`。这是四个样例里最接近数学绘图的一张。曲线由 SciPy 直接计算，零点也来自函数求解，不涉及随机数据。

原脚本使用外部 LaTeX 和特定字体。在普通电脑上复现时，这两项最容易报错。此次改用 Matplotlib 自带的数学文字，保留函数标签、零点和关键注释，不需要额外安装 LaTeX。

### 数据怎么来的

这里使用 SciPy 计算，没有人工录入的数据集。自变量从0到20，共1200个点，通过 `scipy.special.jv` 计算 J0 至 J4；各阶零点由 `jn_zeros` 求出，只保留小于20的部分。参考源文件是 bessel-functions.py。

![Image](https://mmbiz.qpic.cn/sz_mmbiz_png/UMphHEBOGsN1TqGXIZoxdgg9OMk2iaNhjbV9Lr930WQpmtObOiceIHfKOGypU4Qzru0hpbKRz8SPPyl0I14AkwVicSK6lZxjU2DfUJgf50KeXI/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=6)

### 提示词

> 使用 scientific-visualization 参考 bessel-functions.py 绘制J0到J4。x从0到20取1200个点，用scipy.special.jv计算曲线，用jn_zeros求每阶前8个零点，只显示小于20的零点。不要依赖外部LaTeX或指定字体，改用Matplotlib数学文字。直接标出函数阶数，零点用空心圆。导出PNG、可编辑SVG、曲线CSV、零点CSV和运行参数。

![SciPy 计算得到的 J0 至 J4 曲线及零点。图形展示数学计算结果，不是实验测量。](https://mmbiz.qpic.cn/mmbiz_png/UMphHEBOGsMwJ1zjqtAOIPw1bgENHW0sjSQLt1uibVxibxGRzeAbT8icMg9WwHakR4xvdSqCRFfxP3gSMZSF4IPzNo3Ex2lWeMfdyLK1DXv4bM/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=7)SciPy 计算得到的 J0 至 J4 曲线及零点

这里能看出 Skill 很实用的一面。外部字体缺失时，它仍然保留可运行代码和可编辑矢量输出。以后改阶数、区间或注释位置，可以直接从源文件继续改。

## 六、样例④-极坐标方向分布

第四张参考 `code/scales-projections/projection-polar-histogram.py`。极坐标图适合方向、角度和周期数据，刻度、半径与角度标签也最容易做得拥挤。

此次使用固定随机种子生成方向频数，只用于展示构图。Skill 保留圆周刻度和方向分布，减少过密装饰，把角度与扇区频数的含义写清楚。

### 数据怎么来的

这张图同样是合成演示。角度从0度到350度，每10度一个扇区，共36行。随机种子固定为123，频数按 `24+15cos(θ-0.7)+7cos(2θ+0.4)` 计算，再加上负3至3的整数扰动，最低截到4。原书结构来自 projection-polar-histogram.py。

### 提示词

> 使用 scientific-visualization 参考 projection-polar-histogram.py 制作方向频率极坐标图。数据是固定seed=123的合成演示，从0度到350度，每10度一行。半径表示每个扇区的频数，0度放在北方，角度顺时针增加。减少过密刻度和装饰，不能写成真实风向结果。导出PNG、可编辑SVG、36行CSV、随机种子和分箱说明。

![确定性合成的方向频数演示。半径表示每10度扇区的频数，不代表真实风场或实验样本。](https://mmbiz.qpic.cn/mmbiz_png/UMphHEBOGsMPCJB6b3nID9M5RcpE2DWb50ibqwt3BZKt1ERTzJwnFjXicvXrDZcicyWRhibqu61fSw7XXclQZaWhZHBNibHv2MHUO6WdxVcibGpgE/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=8)半径表示每10度扇区的频数

真实使用时，把合成数组换成自己的方向数据，还要说明分箱宽度、观测数量与缺失方向怎样处理。只把图形换得漂亮，不能替代这些信息。

## 七、复刻时最值得保留的四件事

我这次没有追求像素级照搬。我保留原书代码中的构图办法，再让它适合自己的数据和交付场景。

我现在会把代码和数据一起交给 Agent，不让它看图猜数值。合成数据在图注里写明，哪些数值不能动也提前说清楚。输出时同时要 PNG、SVG 和运行记录，拿到图片以后再缩到手机宽度看一遍。电脑屏幕上的正常字号，放进公众号后常常太小。

`scientific-visualization` 做得好的地方也在这里。它能约束过程，减少常见绘图错误，最终判断仍要由作者完成。自动导出通过，不等于期刊格式已经通过；准备投稿时还要查看目标期刊当时的图件要求。

## 从基础稿接到科研绘图

如果手里还没有一份完整初稿，可以先用千笔- AIWritePaper 整理选题、大纲与可修改的论文基础稿，再把已有数据和图表交给Codex深入处理。

两者适合分开干活。

千笔- AIWritePaper

帮你把材料组织成基础稿，绘图Skill负责数据图的表达、导出与检查，当然千笔-AIWritePaper本身的科研绘图的质量就相当高！。


---

## 图片来源映射

| 文件 | 原始 URL |
|---|---|
| images/01.png | https://mmbiz.qpic.cn/mmbiz_png/UMphHEBOGsNNj75pNG6OpjxeqOcwHnPdlAroXohTTVzQzApWb0zmfsxVCFAFicryoag5xdvKJkqfUcAqyyD9liarZ4TD0pnVRPbhBSzrZUzW0/0?wx_fmt=png |
| images/02.png | https://mmbiz.qpic.cn/mmbiz_png/UMphHEBOGsOGaicH2WtXFK2WelWUEXf2q5jdD8XVRMKNdpmHEiahm416gIibONGYu7nG4CpLMNc4N1Ez46zDiaze2FHfOg2ibX7A2Ja8weBdKOdI/0?wx_fmt=png |
| images/03.png | https://mmbiz.qpic.cn/mmbiz_png/UMphHEBOGsMW0mawjne75k58RdKfjem01Q1reXqTmSjG9ZzKtRzguhKFhVhv3aYiaQGSibHpiasXfQrQyQj4090icyP7YlAHTQ99WKcO6gH0zIk/0?wx_fmt=png |
| images/04.png | https://mmbiz.qpic.cn/sz_mmbiz_png/UMphHEBOGsMzmicdj6NDqKFFRTvDVbHmetGuDNLOR0Jib5IbS5M1mWgiasc4PJc5hJI6PhyemJU3YgjGVg9ggsZicLuhRcn8kVMNlNMCPam4yWw/0?wx_fmt=png |
| images/05.png | https://mmbiz.qpic.cn/sz_mmbiz_png/UMphHEBOGsPvaZ8MY4vGictnCSz9iagVj7PVYReACRb2tLWLnjeyXRicroPw2FTKgkZrdBbLssRcfWogic81A3cKtq5x1zX4MsAngCicJhuHTpC0/0?wx_fmt=png |
| images/06.png | https://mmbiz.qpic.cn/mmbiz_png/UMphHEBOGsNkXQ0UaluncX2ibuVLjHNjO6Vt2ejibuoh94ju7UsBql0OuugVV0hemhTM5OMGaeTfBicJ1icCHbqlicyspAqSuRmSdViaiaE981SqxQ/0?wx_fmt=png |
| images/07.png | https://mmbiz.qpic.cn/sz_mmbiz_png/UMphHEBOGsN1TqGXIZoxdgg9OMk2iaNhjbV9Lr930WQpmtObOiceIHfKOGypU4Qzru0hpbKRz8SPPyl0I14AkwVicSK6lZxjU2DfUJgf50KeXI/0?wx_fmt=png |
| images/08.png | https://mmbiz.qpic.cn/mmbiz_png/UMphHEBOGsMwJ1zjqtAOIPw1bgENHW0sjSQLt1uibVxibxGRzeAbT8icMg9WwHakR4xvdSqCRFfxP3gSMZSF4IPzNo3Ex2lWeMfdyLK1DXv4bM/0?wx_fmt=png |
| images/09.png | https://mmbiz.qpic.cn/mmbiz_png/UMphHEBOGsMPCJB6b3nID9M5RcpE2DWb50ibqwt3BZKt1ERTzJwnFjXicvXrDZcicyWRhibqu61fSw7XXclQZaWhZHBNibHv2MHUO6WdxVcibGpgE/0?wx_fmt=png |
