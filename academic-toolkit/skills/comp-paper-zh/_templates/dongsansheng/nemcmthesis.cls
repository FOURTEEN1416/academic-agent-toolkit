%
% This is file "nemcmthesis.cls"
%
% Copyright (C) 2023-2024 by JL <yhlaozero2@163.com>
%
% This work may be distributed and/or modified under the
% conditions of the LaTeX Project Public License, either version 1.3
% of this license or (at your option) any later version.
% The latest version of this license is in
%   https://www.latex-project.org/lppl.txt
% and version 1.3c or later is part of all distributions of LaTeX
% version 2008 or later.
%



% --------------- 全局设置 --------------- %
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{nemcmthesis}[2025/05/01 v2.0.0 Unofficial LaTeX Template for Northeastern-Three-Provinces Mathematical Contest in Modeling]
% ======================================== %


% --------------- 编译器约束 --------------- %
\RequirePackage{ifxetex}
\RequireXeTeX
\ifxetex\else
\ClassError{nemcmthesis}{You must use the `xelatex' driver\MessageBreak Please choose `xelatex'}{%
Just choose `xelatex', no `pdflatex' or `latex' and so on.}
\fi
% ======================================== %


% ---------- 文档类声明命令的可选参数初始化 ---------- %
\newif\if@nemcmthesis@coverpage %【封面页控制，初始值为真，下同】

\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ProcessOptions\relax %【这句万万不可改动】
\LoadClass[a4paper]{article} %【导入正规文档类】
% ======================================== %


% --------------- ctex宏集设置 --------------- %
\RequirePackage[UTF8, heading=true, zihao = -4]{ctex}
% ⛔ 固定中文引号字体：防加粗段引号跟随 \textbf→黑体、开引号字形像后引号。
%   独立引号族 zhquote(宋体)+newunicodechar，加粗/西文环境字形都开闭分明。
%   ⛔ 用 \setCJKfamilyfont+\CJKfamily 机制(加粗段有效)，不用 \newCJKfontfamily(加粗段失效)。
\setCJKfamilyfont{zhquote}[AutoFakeBold]{SimSun}
\RequirePackage{newunicodechar}
\newunicodechar{“}{{\CJKfamily{zhquote}\char"201C}}
\newunicodechar{”}{{\CJKfamily{zhquote}\char"201D}}
\newunicodechar{‘}{{\CJKfamily{zhquote}\char"2018}}
\newunicodechar{’}{{\CJKfamily{zhquote}\char"2019}}
\ctexset{
  abstractname = {\zihao{4}摘~ 要},
  bibname = \hfill{\zihao{4}参~ 考~ 文~ 献}\hfill,
  section = {
    format = {\centering\bfseries},
    name = {,、},
    number = \chinese{section},
    beforeskip=15bp,
    afterskip=10bp,
    aftername={},
  },
  subsection={
    format={\bfseries},
    beforeskip=15bp,
    afterskip=10bp,
  },
  subsubsection={
    format={\bfseries},
    beforeskip=15bp,
    afterskip=10bp,
  }
}
% ======================================== %


% --------------- 原有的标题页三要素设置为空 --------------- %
\title{}
\author{}
\date{}
% ======================================== %


% --------------- 颜色定制 --------------- %
\RequirePackage[table]{xcolor} %颜色定制
\definecolor{keywordincode}{RGB}{000,000,255}
\definecolor{stringincode}{RGB}{128,128,000}
\definecolor{commentincode}{RGB}{106,153,85}
% ======================================== %


% --------------- 页面样式 --------------- %
\RequirePackage{fancyhdr} %定制页眉页脚
\RequirePackage{geometry} %定制页面
\geometry{top=2.5cm, bottom=2.5cm, left=2.5cm, right=2.5cm, headsep=0.5cm}

\pagestyle{fancy}
\lhead{} %在'heading=true'下，默认左页眉为当前二级标题名称，因此要赋值为空
\rhead{} %'heading=true'下，默认右页眉为当前一级标题名称，，因此要赋值为空
\chead{}
\cfoot{\zihao{-5} \thepage}
\renewcommand{\headrulewidth}{0.4pt} %疑惑：setlength命令不起作用
\renewcommand{\footrulewidth}{0pt}
% ======================================== %


% --------------- 字体 --------------- %
\RequirePackage{fontspec}
%% --------- 英文字体设置 ----------- %
\IfFontExistsTF{Times New Roman}{
    \setmainfont{Times New Roman}
  }{
    \IfFontExistsTF{./misc/times.ttf}{
      \setmainfont{times}[
        Path={./misc/},
        Extension = .ttf,
        UprightFont = times,
        BoldFont = timesbd,
        ItalicFont = timesi,
        BoldItalicFont = timesbi,
      ]
    }{
      \setmainfont{TeX Gyre Termes} %发行版内置字体
    }
  }
%% ================================== %
% ======================================== %


% --------------- 摘要环境 --------------- %
\RequirePackage{abstract}
\setlength{\absleftindent}{0pt} %取消左自动缩进
\setlength{\absrightindent}{0pt} %取消右自动缩进
\renewcommand{\abstracttextfont}{\normalsize} %修改摘要内容的字号
\newcommand{\keywords}[1]{\vspace{\baselineskip}{}\noindent\bfseries 关键词: #1} %插入关键词
% ======================================== %


% --------------- 列表环境 --------------- %
\RequirePackage[inline]{enumitem}
% ======================================== %


% --------------- 数学环境 --------------- %
\RequirePackage{amsmath, amssymb, mathrsfs} %数学公式三件套
\RequirePackage{siunitx} %SI制单位
\DeclareMathOperator{\diff}{\,\mathrm{d}\hspace{-1.5pt}} %微分算子

\RequirePackage{amsthm}

\renewcommand{\proofname}{证明}
\renewenvironment{proof}[1][\proofname]{\par
\pushQED{\qed}%
\normalfont \topsep6\p@\@plus6\p@\relax
\trivlist
\item\relax
{\hspace{\parindent}\rmfamily\bfseries #1\@addpunct{:}}\hspace\labelsep\ignorespaces
}{%
\popQED\endtrivlist\@endpefalse
}

\newtheoremstyle{newthmstyle}
  {3bp} %Space above
  {3bp} %Space below
  {\rmfamily} %Body font
  {\parindent} %Indent amount
  {\bfseries} %Theorem head font
  {} %Punctuation after theorem head
  {1.0em} %Space after theorem head
  {} %Theorem head spec (can be left empty, meaning ‘normal’)
\theoremstyle{newthmstyle}
\newtheorem{Definition}{定义}
\newtheorem{Proposition}{命题}
\newtheorem{Lemma}{引理}
\newtheorem{Theorem}{定理}
\newtheorem{Example}{例}
\newtheorem{Problem}{问题}
\newtheorem{Corollary}{推论}
\newtheorem{Remark}{注}
% ======================================== %


% --------------- 代码环境 --------------- %
\RequirePackage{verbatim} %简易代码环境（提供：verbatim 环境。缺点：不能解决断行问题。）
\RequirePackage{listings} %定制代码环境
\RequirePackage{matlab-prettifier} %MATLAB专门的代码环境
%代码环境定制
\lstset{
  basicstyle=\small\ttfamily, %整体的字号、字体
  stringstyle=\ttfamily, %字符串样式
  backgroundcolor=\color{gray!10}, %背景颜色
  breaklines=true, %自动断行
  showstringspaces=false, %取消特别的字符间距
  framexleftmargin=5bp, %内部左边距
  frame=trbl, %显示各方向的代码框线条
  frameround=tttt, %设置代码框各棱角的形状
  keywordstyle=\color{keywordincode}, %关键字样式
  stringstyle=\color{stringincode}, %字符串样式
  commentstyle=\color{commentincode}, %注释样式
}
% ======================================== %


% --------------- 伪代码 --------------- %
\RequirePackage[ruled, lined]{algorithm2e}
\renewcommand{\algorithmcfname}{算法}
% ======================================== %


% --------------- 标题样式：章、节、条、款、项 --------------- %
\RequirePackage{titlesec}
% ======================================== %


% --------------- 图、表标题样式 --------------- %
\RequirePackage{caption}
\DeclareCaptionLabelSeparator{doublespace}{~~}
\captionsetup{font=small, labelsep=doublespace, labelfont=bf, textfont=bf}
\RequirePackage[labelformat=brace]{subcaption} %(与 subfigure 宏包冲突)也能提供 subfigure 环境（需设置宽度），并使环境中的标题变成副标题样式
% ======================================== %


% --------------- 插图环境 --------------- %
\RequirePackage{graphicx}
\RequirePackage{float} %引入参数H
\graphicspath{{figures/}} %可添加多个母目录，之间用逗号隔开
% ======================================== %


% --------------- 表格环境 --------------- %
\RequirePackage{makecell}
\RequirePackage{booktabs} %【三线表】
\RequirePackage{longtable} %【跨页表格】
\RequirePackage{tabularx} %【定制表格宽度】
\RequirePackage{multirow} %【实现表格行合并】
\RequirePackage{diagbox} %【表头反斜线】
\RequirePackage{bigstrut} %【在跨行表格中输入定界符】
\RequirePackage{makecell} %【封面表格横线的宽度】
\RequirePackage{multicol} %【实现双栏/多栏环境】
% ======================================== %


% --------------- 调整行间距 --------------- %
\RequirePackage{setspace}
% ======================================== %


% --------------- 杂项 --------------- %
\RequirePackage{titletoc} % 设置目录样式（但辽省赛不需要目录）
\RequirePackage{comment} % 提供注释环境
\RequirePackage{lipsum, zhlipsum} %随机文本（用于调试）
% ======================================== %


% --------------- 参考文献 --------------- %
\RequirePackage[numbers,square,comma,sort&compress]{natbib}
\RequirePackage{gbt7714}
\setlength{\bibsep}{0bp}
\bibliographystyle{gbt7714-numerical}
\newcommand{\upcite}[1]{\textsuperscript{\cite{#1}}} % 上标形式的引用
% ======================================== %


% --------------- 附录与自定义附录 --------------- %
\RequirePackage{appendix} %设置附录样式
% ======================================== %


% ------------------------- 关于论文信息的全局变量导入 ------------------------- %
\RequirePackage{ifthen} %【引入条件判断逻辑】
%% -------------------- 图片&表格 -------------------- %
\RequirePackage{array} %【与表格相关】
%% ============================================================ %


%% -------------------- 变量预定义 -------------------- %
\newcommand{\ttleinMAINBODY}{~} %【论文题目】
\newcommand{\nemcmthesis@tokens@category}{~} %【参赛组别】
\newcommand{\nemcmthesis@tokens@school}{~} %【参赛学校】
\newcommand{\nemcmthesis@tokens@tihao}{~} %【参赛题号】
\newcommand{\nemcmthesis@tokens@membera}{~} %【队员1姓名】
\newcommand{\nemcmthesis@tokens@memberb}{~} %【队员2姓名】
\newcommand{\nemcmthesis@tokens@memberc}{~} %【队员3姓名】
\newcommand{\nemcmthesis@tokens@phonea}{~} %【队员1联系电话】
\newcommand{\nemcmthesis@tokens@phoneb}{~} %【队员2联系电话】
\newcommand{\nemcmthesis@tokens@phonec}{~} %【队员3联系电话】
\newcommand{\nemcmthesis@tokens@supervisor}{~} %【指导教师】
%% ============================================================ %

%% -------------------- 正式变量定义 -------------------- %
\newcommand{\ttle}[1]{\renewcommand{\ttleinMAINBODY}{#1}} %【论文题目】
\newcommand{\school}[1]{\renewcommand{\nemcmthesis@tokens@school}{#1}} %【参赛学校】
\newcommand{\category}[1]{\renewcommand{\nemcmthesis@tokens@category}{#1}} %【参赛组别】
\newcommand{\tihao}[1]{\renewcommand{\nemcmthesis@tokens@tihao}{#1}} %【参赛题号】
\newcommand{\membera}[1]{\renewcommand{\nemcmthesis@tokens@membera}{#1}} %【队员姓名A】
\newcommand{\memberb}[1]{\renewcommand{\nemcmthesis@tokens@memberb}{#1}} %【队员姓名B】
\newcommand{\memberc}[1]{\renewcommand{\nemcmthesis@tokens@memberc}{#1}} %【队员姓名C】
\newcommand{\phonea}[1]{\renewcommand{\nemcmthesis@tokens@phonea}{#1}} %【队员1联系电话】
\newcommand{\phoneb}[1]{\renewcommand{\nemcmthesis@tokens@phoneb}{#1}} %【队员2联系电话】
\newcommand{\phonec}[1]{\renewcommand{\nemcmthesis@tokens@phonec}{#1}} %【队员3联系电话】
\newcommand{\supervisor}[1]{\renewcommand{\nemcmthesis@tokens@supervisor}{#1}} %【指导教师】
%% ============================================================ %

% ================================================================================ %


% ------------------------- 封面页的导入 ------------------------- %
\newcommand{\makecoverpage}{
  \thispagestyle{empty} %【无页眉页脚】

~\vspace{60.0pt}

\begin{table}[H]
    \renewcommand\arraystretch{1.5}
    \qquad\qquad\begin{tabular}
      {
      >{\heiti\fontsize{15.0pt}{0pt}\selectfont}b{2.5cm}<{}
      >{\heiti\centering\arraybackslash\fontsize{15.0pt}{0pt}\selectfont }p{5.5cm}<{}
      }
      论文题目： & \nemcmthesis@tokens@tihao \\
      \cline{2-2}\vspace{45.0pt}
      组\hspace{30pt}别： & \nemcmthesis@tokens@category \\
      \cline{2-2}
    \end{tabular}
\end{table}{}\vspace{90.0pt}

\noindent\qquad\qquad{\heiti\fontsize{15.0pt}{0pt}\selectfont ~参赛队员信息：}

\begin{table}[H]
  \renewcommand\arraystretch{2.0}
  \centering
  %\caption{Add caption}
  \begin{tabular}[|c|c|c|c|]
      {
      |>{\heiti\centering\arraybackslash\fontsize{13.5pt}{0pt}\selectfont}m{2.5cm}|
      >{\centering\arraybackslash\fontsize{13.5pt}{0pt}\selectfont} m{4.5cm}|
      >{\centering\arraybackslash\fontsize{13.5pt}{0pt}\selectfont} m{4.5cm}|
      >{\centering\arraybackslash\fontsize{13.5pt}{0pt}\selectfont} m{3.5cm}|
      >{\centering\arraybackslash\fontsize{13.5pt}{0pt}\selectfont} m{2.5cm}|
      }
    \hline
          & {\heiti 姓名} & {\heiti 联系电话}  & {\heiti 指导老师} \bigstrut\\
    \hline
    参赛队员1 & \nemcmthesis@tokens@membera & \nemcmthesis@tokens@phonea & \multirow{3}[6]{*}{\nemcmthesis@tokens@supervisor} \bigstrut\\
    \cline{1-3}
    参赛队员2 & \nemcmthesis@tokens@memberb & \nemcmthesis@tokens@phoneb & \bigstrut\\
    \cline{1-3}
    参赛队员3 & \nemcmthesis@tokens@memberc & \nemcmthesis@tokens@phonec & \bigstrut\\
    \hline
  \end{tabular}%
  %\label{tab:addlabel}%
\end{table}{}\vspace{90.0pt}

\begin{table}[H]
    \renewcommand\arraystretch{1.5}
    \qquad\qquad\begin{tabular}
      {
      >{\fontsize{15.0pt}{0pt}\selectfont}b{2.5cm}<{}
      >{\centering\arraybackslash\fontsize{15.0pt}{0pt}\selectfont }p{6.5cm}<{}
      }
      {\heiti 参赛学校：} &  \\[15pt]
      \multicolumn{2}{c}{\nemcmthesis@tokens@school} \\
      \hline
    \end{tabular}
\end{table}%
\newpage
} %【\newcommand{\makecoverpage}】
% ============================================================ %


% --------------- 对sty,cls的命令的定制 --------------- %
\RequirePackage{etoolbox}

\AddToHook{cmd/makecoverpage/after}{
  \pagestyle{plain} %摘要页设置为无页眉、有页脚的模式
  \pagenumbering{arabic} %从摘要页开始计数，且设为阿拉伯数字页码
  %% ----- 正文行距 ----- %
  % 关键系数k(基础行距换算系数)：1.296875/1.2
  % 实际的伸缩因子：
  % 1.2倍行距: 1.2*k =[approximately]= 1.297
  \linespread{1.297}\selectfont
  %% ==================== %
}
\AddToHook{env/abstract/before}{
  \begin{center}
    {\bfseries\zihao{4}\ttleinMAINBODY}
  \end{center}
}

\AddToHook{env/thebibliography/before}{
  \phantomsection
  \addcontentsline{toc}{section}{参考文献}
}

%% ------- 设置附录样式 --------- %
\AddToHook{env/appendices/begin}[style_in_appendix]{
  \ctexset{
    section = {
      format = {\bfseries},
      name = {附录~,},
      number = {\arabic{section}},
      aftername = {\hspace{1em}},
      beforeskip=0.5ex,
      afterskip=0.5ex,
    }
  }
  \zihao{5}
}
\AddToHook{env/appendices/after}{
  \RemoveFromHook{env/appendices/begin}[style_in_appendix]
}
%% ============================= %

% ======================================== %


% --------------- 超链接与交叉引用 --------------- %
\RequirePackage[hidelinks, bookmarksnumbered=true, bookmarksopen=true, breaklinks=true]{hyperref} %参数bookmarksnumbered使得PDF书签自带编号
% ======================================== %
