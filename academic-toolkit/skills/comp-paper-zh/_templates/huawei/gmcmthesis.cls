\NeedsTeXFormat{LaTeX2e}[1995/12/01]
\ProvidesClass{gmcmthesis}
              [2024-09-17 v2.4 update by andy123t (TB merge: upstream v2.4/2024-09-17 + local patches kept)]
%% Inital Code
\newif\if@gmcm@bwprint\@gmcm@bwprintfalse
\newif\if@gmcm@preface\@gmcm@prefacetrue
% tokens definition
%%%% 承诺书
\newcommand\gmcm@tokens@keywords{}
\newcommand*\gmcm@tokens@tihao{}
\newcommand*\gmcm@tokens@baominghao{}
\newcommand*\gmcm@tokens@schoolname{}
\newcommand*\gmcm@tokens@membera{}
\newcommand*\gmcm@tokens@memberb{}
\newcommand*\gmcm@tokens@memberc{}
\newcommand*\gmcm@tokens@supervisor{}
\newcommand*\gmcm@tokens@yearinput{}
\newcommand*\gmcm@tokens@monthinput{}
\newcommand*\gmcm@tokens@dayinput{}
%%%% 编号专用页
% 没有
%% Declaration of Options
\DeclareOption{colorprint}{\@gmcm@bwprintfalse}
\DeclareOption{bwprint}{\@gmcm@bwprinttrue}
\DeclareOption{withoutpreface}{\@gmcm@prefacefalse}
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{ctexart}}
%% Executing of Options
\ExecuteOptions{colorprint}
\ProcessOptions\relax
%% %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%Loading Class
% v2.4 上游改动：cs4size → zihao=-4（2024-09-17 合并轮吸收）
\LoadClass[a4paper,zihao=-4]{ctexart}
%% %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%Loading Package
\RequirePackage{ifxetex}
\RequireXeTeX
\ifxetex\else
\ClassError{mcmthesis}{You must use the `xelatex' driver\MessageBreak Please choose `xelatex'}{%
Just choose `xelatex', no `pdflatex' or `latex' and so on.}
\fi
% 页面布局
\RequirePackage{geometry}
% 数学宏包
\RequirePackage{amsmath}
\RequirePackage{amsfonts}
\RequirePackage{amssymb}
\RequirePackage{bm}
% 设置颜色
\RequirePackage{color,xcolor}
% 插入图片
\RequirePackage{graphicx}
% 表格
\RequirePackage{tabularx,array}
% 调整单元格格式
\RequirePackage{makecell}
%% 长表格
\RequirePackage{longtable}
%% booktabs 提供了\toprule 等命令.
\RequirePackage{booktabs}
%% multirow 支持在表格中跨行
\RequirePackage{multirow}
%% 调整间隔, 让表格更好看些
\RequirePackage{bigstrut}
%% 在跨行表格中输入定界符
\RequirePackage{bigdelim}
% 保护脆落命令
\RequirePackage{cprotect}
% 设置代码环境
% v2.4 上游改动：listings,color → listings,xcolor（xcolor 本文件前已加载，等价清理）
\RequirePackage{listings,xcolor}

% Matlab highlight color settings
%\definecolor{mBasic}{RGB}{248,248,242}       % default
\definecolor{mKeyword}{RGB}{0,0,255}          % bule
\definecolor{mString}{RGB}{160,32,240}        % purple
\definecolor{mComment}{RGB}{34,139,34}        % green
\definecolor{mBackground}{RGB}{245,245,245}   % lightgrey
\definecolor{mNumber}{RGB}{128,128,128}       % gray

% Python highlight color settings
%\definecolor{pBasic}{RGB}{248, 248, 242}     % default
\definecolor{pKeyword}{RGB}{228,0,128}        % magenta
\definecolor{pString}{RGB}{148,0,209}         % purple
\definecolor{pComment}{RGB}{117,113,94}       % gray
\definecolor{pIdentifier}{RGB}{166, 226, 46}  %
\definecolor{pBackground}{RGB}{245,245,245}   % lightgrey
\definecolor{pNumber}{RGB}{128,128,128}       % gray

\lstnewenvironment{Matlab}[1]{
\lstset{language=matlab,               % choose the language of the code
  xleftmargin=20pt,
  xrightmargin=20pt,
  frame=tlbr,framesep=4pt,framerule=0.5pt, % sets the frame style
  %frame=shadowbox,rulesepcolor=\color{red!20!green!20!blue!20},
  basicstyle=\small\fontspec{Courier New},
  keywordstyle={\color{mKeyword}},     % sets color for keywords
  stringstyle={\color{mString}},       % sets color for strings
  commentstyle={\color{mComment}},     % sets color for comments
  backgroundcolor=\color{gray!5},%\color{pBackground}, % choose the background color
  rulecolor=\color{gray!50},
  title=#1,                            % \lstname show the filename of files
  keywords={break,case,catch,classdef,continue,else,elseif,end,for,
  function,global,if,otherwise,parfor,persistent,return,spmd,switch,try,while},
  showspaces=false,                    % show spaces adding particular underscores
  showstringspaces=false,              % underline spaces within strings
  showtabs=false,                      % show tabs within strings adding particular underscores
  tabsize=4,                           % sets default tabsize to 2 spaces
  captionpos=t,                        % sets the caption-position to bottom
  breaklines=true,                     % sets automatic line breaking
}}{}

\lstnewenvironment{Python}[1]{
\lstset{language=python,               % choose the language of the code
  xleftmargin=20pt,
  xrightmargin=20pt,
  frame=single,framesep=4pt,framerule=0.5pt, % sets the frame style
  %frame=shadowbox,rulesepcolor=\color{red!20!green!20!blue!20},
  basicstyle=\small\ttfamily,          % sets font style for the code
  %basicstyle=\footnotesize\fontspec{Consolas},
  keywordstyle=\color{pKeyword},       % sets color for keywords
  stringstyle=\color{pString},         % sets color for strings
  commentstyle=\color{pComment},       % sets color for comments
  backgroundcolor=\color{gray!5},%\color{pBackground}, % choose the background color
  rulecolor=\color{gray!50},
  title=#1,                            % \lstnames how the filename of files
  emph={format_string,eff_ana_bf,permute,eff_ana_btr},
  emphstyle=\color{pIdentifier}
  showspaces=false,                    % show spaces adding particular underscores
  showstringspaces=false,              % underline spaces within strings
  showtabs=false,                      % show tabs within strings adding particular underscores
  tabsize=4,                           % sets default tabsize to 2 spaces
  captionpos=t,                        % sets the caption-position to bottom
  breaklines=true,                     % sets automatic line breaking
}}{}

% ---------- v2.4 上游吸收：全局 lstset（2024-09-17 合并轮） ----------
% 上游注释掉的 dkgreen/mauve 定义在此激活，否则 \commentstyle/\stringstyle 引用未定义颜色
\definecolor{dkgreen}{rgb}{0,0.6,0}
\definecolor{mauve}{rgb}{0.58,0,0.82}
\lstset{
  frame=tb,
  xleftmargin=25pt,
  aboveskip=3mm,
  belowskip=3mm,
  showstringspaces=false,
  columns=flexible,
  framerule=1pt,
  rulecolor=\color{gray!35},
  backgroundcolor=\color{gray!5},
  basicstyle={\small\ttfamily},
  numbers=none,
  numberstyle=\tiny\color{gray},
  keywordstyle=\color{blue},
  commentstyle=\color{dkgreen},
  stringstyle=\color{mauve},
  breaklines=true,
  breakatwhitespace=true,
  tabsize=3,
}

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% 二 设置页面
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% 首行缩进
\RequirePackage{indentfirst}
% 设置浮动体的标题
\RequirePackage{caption}
% 定制列表环境
\RequirePackage{enumitem}
% 下划线
\RequirePackage[normalem]{ulem}
% 尺寸计算
\RequirePackage{calc}
\RequirePackage{titletoc,url}
%参考文献
\RequirePackage[numbers]{natbib}
\setlength{\bibsep}{0pt plus 0.3ex}

\RequirePackage{etoolbox}
\AtBeginEnvironment{thebibliography}{%
    \phantomsection
    \addcontentsline{toc}{section}{\refname}
    }
% 超链接 hyperref 的设置
\RequirePackage{hyperref}
%% Document Layout
% 页面布局
\geometry{top=30.0mm,bottom=25.0mm,left=22.5mm,right=22.5mm,headsep=8mm}
% \geometry{top=30.0mm,bottom=25.0mm,left=31.7mm,right=31.7mm,headsep=8mm}
\renewcommand*{\baselinestretch}{1.38}
% \renewcommand*{\baselinestretch}{1}
% 修改tabular 环境, 设置表格中的行间距为正文行间距.
\let\gmcm@oldtabular\tabular
\let\gmcm@endoldtabular\endtabular
\renewenvironment{tabular}%
	{\bgroup%
	\renewcommand{\arraystretch}{1.38}%
	\gmcm@oldtabular}%
	{\gmcm@endoldtabular\egroup}
% 每行缩进两个汉字
\setlength\parindent{2em}

% ----------
% 删减一小段数学环境
% -----------

% 浮动环境设置
% 默认情况下, \LaTeX{} 要求每页的文字至少占据 20%,否则该页就只单独放置一个浮动环境,
% 而这通常不是我们想要的, 我们将这个要求降低到 5%.
 \renewcommand*{\textfraction}{0.05}
% 有时如果多个浮动环境连续放在一起, \LaTeX{}
% 会将它们分在几个不同页，即使它们可在同一页放
% 得下. 我们可以通过修改 |\topfraction| 和 |\bottomfraction| 分别设置顶端和底端的浮
% 动环境的最大比例.
 \renewcommand*{\topfraction}{0.9}
 \renewcommand*{\bottomfraction}{0.8}
% 有时\LaTeX{}会把一个浮动环境单独放在一页,
% 我们要求这个环境至少要占据 85% 才能单独放在一页.
% 注意:  |\floatpagefraction| 的数值必须小于 |\topfraction|.
 \renewcommand*{\floatpagefraction}{0.85}
% 关于图片 graphicx
 % 如果图片没有指定后缀, 依次按下列顺序搜索
\DeclareGraphicsExtensions{.pdf,.eps,.jpg,.png}
 % 设置图表搜索路径, 可以给图表文件夹取如下名字
\graphicspath{{figures/}{figure/}{pictures/}%
  {picture/}{pic/}{pics/}{image/}{images/}}

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% 三 设置字体
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
\setmainfont{Times New Roman}
\setmonofont{Courier New}
\setsansfont{Arial}

\setCJKmainfont[AutoFakeBold = {2.15},ItalicFont={KaiTi}]{SimSun}
% ⛔ 固定中文引号字体：防加粗段引号跟随 \textbf→黑体、开引号字形像后引号。
%   独立引号族 zhquote(宋体)+newunicodechar，加粗/西文环境字形都开闭分明。
\setCJKfamilyfont{zhquote}[AutoFakeBold]{SimSun}
\RequirePackage{newunicodechar}
\newunicodechar{“}{{\CJKfamily{zhquote}\char"201C}}
\newunicodechar{”}{{\CJKfamily{zhquote}\char"201D}}
\newunicodechar{‘}{{\CJKfamily{zhquote}\char"2018}}
\newunicodechar{’}{{\CJKfamily{zhquote}\char"2019}}
\setCJKfamilyfont{zhkai}[AutoFakeBold=2.15]{KaiTi}
\setCJKsansfont[AutoFakeBold=2.15]{SimHei}
\setCJKfamilyfont{zhsong}[AutoFakeBold=2.15]{SimSun}
\setCJKfamilyfont{zhhei}[AutoFakeBold=2.15]{SimHei}

\ifx\lishu\undefined%
\setCJKfamilyfont{zhli}{LiSu}
\newcommand*{\lishu}{\CJKfamily{zhli}} %% Do this if it is undefined
\else
%% Do this if it is defined
\fi


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% 四 设置图表
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% 图表标题
\DeclareCaptionFont{song}{\CJKfamily{zhsong}}
\DeclareCaptionFont{minusfour}{\zihao{-4}}
\captionsetup[figure]{%
	format=hang,   % 标题从第二行开始都有缩进, 应该和 justification=raggedright 的效果一样.
	labelsep=quad, % 分隔符是一个空格
	font={song,minusfour,bf}, % 图的字体, 宋体小四
	position=bottom % position=bottom, 不代表标题放在下面, 标题仍放在你放\caption的位置.
}
\captionsetup[table]{%
	format=hang,   % 标题从第二行开始都有缩进, 应该和 justification=raggedright 的效果一样.
	labelsep=quad, % 分隔符是一个空格
	font={song,minusfour,bf}, % 表的字体, 宋体小四
	position=top % position=bottom, 不代表标题放在下面, 标题仍放在你放\caption的位置.
}
% 列表环境设置
\setlist{%
	topsep=0.3em, % 列表顶端的垂直空白
	partopsep=0pt, % 列表环境前面紧接着一个空白行时其顶端的额外垂直空白
	itemsep=0ex plus 0.1ex, % 列表项之间的额外垂直空白
	parsep=0pt, % 列表项内的段落之间的垂直空白
	leftmargin=1.5em, % 环境的左边界和列表之间的水平距离
	rightmargin=0em, % 环境的右边界和列表之间的水平距离
	labelsep=0.5em, % 包含标签的盒子与列表项的第一行文本之间的间隔
	labelwidth=2em % 包含标签的盒子的正常宽度；若实际宽度更宽，则使用实际宽度。
}

% 超链接
% \AtBeginDocument{%
	 \hypersetup{%
		% % unicode=false, % hyperref 和 xetex 同时使用时不能开启 Unicode 选项.
		 hyperfootnotes=true,
		 hyperindex=true,
		 colorlinks=true,
		 bookmarksnumbered=true,
		 bookmarksopen=true,
 		 bookmarksopenlevel=0,
		 allcolors=black,
		 breaklinks=true}%
% }
% \if@gmcm@bwprint
% \AtBeginDocument{\hypersetup{hidelinks}}
% \else\relax\fi
\def\UrlAlphabet{%
      \do\a\do\b\do\c\do\d\do\e\do\f\do\g\do\h\do\i\do\j%
      \do\k\do\l\do\m\do\n\do\o\do\p\do\q\do\r\do\s\do\t%
      \do\u\do\v\do\w\do\x\do\y\do\z\do\A\do\B\do\C\do\D%
      \do\E\do\F\do\G\do\H\do\I\do\J\do\K\do\L\do\M\do\N%
      \do\O\do\P\do\Q\do\R\do\S\do\T\do\U\do\V\do\W\do\X%
      \do\Y\do\Z}
\def\UrlDigits{\do\1\do\2\do\3\do\4\do\5\do\6\do\7\do\8\do\9\do\0}
\g@addto@macro{\UrlBreaks}{\UrlOrds}
\g@addto@macro{\UrlBreaks}{\UrlAlphabet}
\g@addto@macro{\UrlBreaks}{\UrlDigits}

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% 四 设置封面 摘要 目录
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%
% 封面
%%%%%%%%%%%%%%%%%%%%%%%%
% 生成封面, 使用\maketitle
\renewcommand{\maketitle}{\par
	\begingroup
      \newpage
      \global\@topnum\z@ % Prevents figures from going at top of page.
      \ge@maketitle      %
    \endgroup
  \global\let\thanks\relax
  \global\let\maketitle\relax
  \global\let\@maketitle\relax
  \global\let\@thanks\@empty
  \global\let\@author\@empty
  \global\let\@date\@empty
  \global\let\@title\@empty
  \global\let\title\relax
  \global\let\author\relax
  \global\let\date\relax
  \global\let\and\relax
}
\def\ge@maketitle{%
  \clearpage
  % v2.4 上游吸收（首页页码修复）：封面页 thispagestyle plain → empty，
  % 并移除 setcounter{page}{0}/\thepage{0} hack；正文页码仍由 \makenametitle 置 1。
  \thispagestyle{empty}%
  \pdfbookmark[1]{封~面}{cover}
  \if@gmcm@preface

 \begin{center}
 {\includegraphics{logo}}

  \vskip1.5cm
 {\zihao{2} \gmcm@ges@string@contents \par}
 \end{center}

 \vskip4em

 % \thispagestyle{gmcmheadings}
 \renewcommand\arraystretch{1.5}
 %\noindent 
 \begin{tabularx}{\textwidth-40pt}{lX}
  \zihao{-2}\bfseries 学\qquad 校&\zihao{-2}\bfseries\gmcm@tokens@schoolname\\
  \Xhline{1.2pt}\\
  \zihao{-2}\bfseries 参赛队号&\zihao{-2}\bfseries\gmcm@tokens@baominghao\\
  \Xhline{1.2pt}\\[-15pt]
   \multirow{3}{*}{\zihao{-2}\bfseries 队员姓名}&\zihao{-2}\bfseries   1. \gmcm@tokens@membera\hfill\null\\
   \cline{2-2}\\[-15pt]
                               &\zihao{-2}\bfseries 2. \gmcm@tokens@memberb\hfill\null\\
   \cline{2-2}\\[-15pt]
                        &\zihao{-2}\bfseries 3.  \gmcm@tokens@memberc\hfill\null\\
   \Xhline{1.2pt}
  \end{tabularx}

	\makenametitle
	}

\def\makenametitle{
\clearpage
\thispagestyle{plain}%
\pdfbookmark[1]{标~题}{title}
\setcounter{page}{1}
\begin{center}
%{\includegraphics[width=4cm]{logo}}
{\zihao{2} \gmcm@ges@string@contents \par}
\end{center}

\vskip0.6cm%

\begin{center}
\begin{tabularx}{.95\textwidth}{@{}lX@{}}
% v2.4 上游吸收（封面更新）：题目行改为 -2 号隶书标签样式 + 题后 \vskip0.2cm
{\zihao{-2}\lishu 题\quad 目: } &
{\zihao{3}\heiti
  % ⛔ 本地补丁保留 (v1.5.0)：用 parbox 包住，让题目自动换行（X 列按宽度换）+ \\ 强制换行也能保持字号一致
  % 之前直接 \@title 时，AI 写的 \\ 第二行会掉出 tabularx 表格，变成正文 12pt 字号
  \parbox[t]{\linewidth}{\centering \@title}}\hfill\null\\
\cline{2-2}
\end{tabularx}
\end{center}

\vskip0.2cm%
}


% 中文标题格式设置
% 目录深度
\setcounter{secnumdepth}{3}
\def\@seccntformat#1{\csname the#1\endcsname\ \ }
% 节标题格式, 居中, 使用\chinese命令修改计数器, \kern 使得数字和内容不至于太远
\newcommand{\thinskip}{\hskip 0.05em\relax}
 \renewcommand\thesection{\arabic{section}\thinskip.}
\renewcommand\thesubsection{\arabic{section}\thinskip.\thinskip\arabic{subsection}}
\renewcommand\thesubsubsection{\thesubsection\thinskip.\thinskip\arabic{subsubsection}}
\renewcommand\section{\@startsection{section}{1}{\z@}%
 	{2.5ex \@plus -1ex \@minus -.2ex}%
	{2.3ex \@plus.2ex}%
	{\bfseries\centering\zihao{4}\heiti}}
\renewcommand\subsection{\@startsection{subsection}{2}{\z@}%
	{1.25ex\@plus -1ex \@minus -.2ex}%
	{1.25ex \@plus .2ex}%
	{\normalfont\normalsize\bfseries}}
\renewcommand\subsubsection{\@startsection{subsubsection}{3}{\z@}%
	{1.25ex\@plus -1ex \@minus -.2ex}%
	{1.2ex \@plus .2ex}%
	{\normalfont\normalsize\bfseries}}
\renewcommand\paragraph{\@startsection{paragraph}{4}{\z@}%
	{3.25ex \@plus1ex \@minus.2ex}%
	{-1em}%
	{\normalfont\normalsize\bfseries}}
\renewcommand\subparagraph{\@startsection{subparagraph}{5}{\parindent}%
	 {3.25ex \@plus1ex \@minus .2ex}%
	 {-1em}%
	 {\normalfont\normalsize\bfseries}}
%%%%%%%%%%%%%%%%%%%%%%%%
% 摘要
%%%%%%%%%%%%%%%%%%%%%%%%
%% 摘要两个字设置为 4 号.
%% 定义摘要环境
\renewenvironment{abstract}{%
\if@twocolumn
		\section*{\gmcm@cap@abstractname}%
	\else
	 \begin{center}%
	{\zihao{3}\lishu\gmcm@cap@abstractname\vspace{\z@}}%
	 \end{center}%
 	 \quotation
	\fi}
	{\if@twocolumn\else\endquotation\clearpage\fi}
% ⛔ 修复摘要后空白页：原本 \newpage\null 在 abstract 接近页底时会产生
%    只含 \null 的空白页（封面后第 2 页变空白）。改用 \clearpage 后：
%    - \clearpage 清空 float 队列，强制换页一次
%    - 不留 \null 空盒，新页直接由后续内容（目录/正文）填充
%    - main.tex 的目录前 \newpage / \clearpage 仍可保留作为双保险
\renewenvironment{quotation}
	{\list{}{\listparindent 2em%
	 \itemindent \listparindent
	 \rightmargin\z@
	 \leftmargin\z@
	 \parsep \z@ \@plus\p@}%
	\item\relax}
	{\endlist}

\newcommand\keywords[1]{%
	\renewcommand{\gmcm@tokens@keywords}{#1}
	\par
	\vskip1ex
	{\noindent\zihao{-4}\heiti\gmcm@cap@keywordsname：}~{\gmcm@tokens@keywords}
	}


\newcommand*\baominghao[1]{%
	\renewcommand{\gmcm@tokens@baominghao}{#1}}
\newcommand*\schoolname[1]{%
	\renewcommand{\gmcm@tokens@schoolname}{#1}}
\newcommand*\membera[1]{%
	\renewcommand{\gmcm@tokens@membera}{#1}}
\newcommand*\memberb[1]{%
	\renewcommand{\gmcm@tokens@memberb}{#1}}
\newcommand*\memberc[1]{%
	\renewcommand{\gmcm@tokens@memberc}{#1}}
%%%%%%%%%%%%%%%%%%%%%%%%
% 其他
%%%%%%%%%%%%%%%%%%%%%%%%

% ----------
% 删减一小段定理
% -----------

  %%%  中文标题名称
 \newcommand*{\gmcm@cap@abstractname}{摘\qquad\quad 要： }
  %%%  中文关键字
 \newcommand*{\gmcm@cap@keywordsname}{关键词}
 
  %%%常量
 \newcommand\gmcm@ges@string@contents{\includegraphics{title}}
 %\newcommand\gmcm@ges@string@contents{\includegraphics[width=11cm]{title}}++++++++++++++++++
 \renewcommand{\thetable}{\arabic{section}.\arabic{table}}
 \renewcommand{\theequation}{\arabic{section}.\arabic{equation}}
 \renewcommand{\thefigure}{\arabic{section}.\arabic{figure}}
 
 % %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%% 字图与子标题
 % \RequirePackage{subcaption}
 \RequirePackage[titles]{tocloft}
 %\renewcommand{\cftdot}{$\cdot$}
 %\renewcommand{\cftsecdotsep}{1.5}
 \renewcommand{\cftsecdotsep}{4.5}
 \setlength{\cftbeforesecskip}{7pt}
 \setlength{\cftbeforesubsecskip}{3pt}
 %\setlength{\cftbeforesubsecskip}{5pt}
 \renewcommand{\cftsecfont}{\bfseries\zihao{-4}\heiti}
 \renewcommand{\cftsecleader}{\cftdotfill{\cftsecdotsep}}
 \renewcommand{\cftsecaftersnumb}{\hskip.4em}
%%%%%%%%%%%%%%%%%%%%%%%%
% 目录
%%%%%%%%%%%%%%%%%%%%%%%%
% ----------- 设置新的生成目录命令 -------------
\newcommand{\maketoc}{
  \phantomsection
  \pdfbookmark[1]{目~录}{contents}
  \tableofcontents
}

\RequirePackage{titletoc}
\RequirePackage[title,titletoc]{appendix}

\newcommand*{\gmcm@cap@appendixname}{附录}
\renewcommand*\appendixname{\gmcm@cap@appendixname}

% 定义附录  
% \let\oldappendix\appendix
\renewcommand\appendix{\par
  \setcounter{section}{0}%
   \setcounter{subsection}{0}%
  \gdef\thesection{\appendixname\@Alph\c@section}
  %\gdef\thesubsection{\@Alph\c@section\thinskip.\thinskip\c@subsection}
}

%%设置目录格式
% 节的目录格式
\titlecontents{section}[0pt]{\vspace{2mm}\bfseries\heiti}
{\thecontentslabel\hskip.5em}{}{\titlerule*[0.5pc]{.}\contentspage}
% 小节的目录格式
\titlecontents{subsection}[30pt]{\songti}
{\thecontentslabel\hskip.5em}{}{\titlerule*[0.5pc]{.}\contentspage}
% 小小节的目录格式
\titlecontents{subsubsection}[55pt]{\songti}
{\thecontentslabel\hskip.5em}{}{\titlerule*[0.5pc]{.}\contentspage}

\pagestyle{plain}

\endinput
