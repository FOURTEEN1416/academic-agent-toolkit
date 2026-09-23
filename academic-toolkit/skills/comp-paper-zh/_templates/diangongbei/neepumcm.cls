%%
%% This is file `neepumcm.cls',
%% -----------------------------------
%%
%% This is a generated file.
%%
%% This work may be distributed and/or modified under the
%% conditions of the LaTeX Project Public License, either version 1.3
%% of this license or (at your option) any later version.
%% The latest version of this license is in
%%   http://www.latex-project.org/lppl.txt
%% and version 1.3 or later is part of all distributions of LaTeX
%% version 2005/12/01 or later.
%%
%% This work has the LPPL maintenance status `maintained'.
%%
%% The Current Maintainer of this work is Liam Huang.
%%
\NeedsTeXFormat{LaTeX2e}[1999/12/01]
\ProvidesClass{neepumcm}
  [2024/05/23 v1 The Thesis Template Designed For neepumcm]
\typeout{The Thesis Template Designed For neepumcm} 
\RequirePackage{xkeyval}
\RequirePackage{etoolbox}
\define@boolkey{MCM}[MCM@opt@]{CTeX}[false]{}
\define@boolkey{MCM}[MCM@opt@]{titlepage}[true]{}
\define@boolkey{MCM}[MCM@opt@]{abstract}[true]{}
\define@boolkey{MCM}[MCM@opt@]{sheet}[true]{}
\define@boolkey{MCM}[MCM@opt@]{titleinsheet}[false]{}
\define@boolkey{MCM}[MCM@opt@]{keywordsinsheet}[false]{}
\define@cmdkeys{MCM}[MCM@opt@]{tcn,problem,timu}
\define@key{MCM}{tcn}[0000]{\gdef\MCM@opt@tcn{#1}}
\define@key{MCM}{problem}[A]{\gdef\MCM@opt@problem{#1}}
\define@key{MCM}{timu}{\gdef\MCM@opt@timu{#1}}
\setkeys{MCM}{tcn=0000,problem=B}

\define@key{yrdmcm.cls}{tcn}[0000]{\gdef\MCM@opt@tcn{#1}}
\define@key{yrdmcm.cls}{problem}[A]{\gdef\MCM@opt@problem{#1}}
\define@key{yrdmcm.cls}{timu}[本科生]{\gdef\MCM@opt@timu{#1}}
\define@boolkey{yrdmcm.cls}[MCM@opt@]{titlepage}{}
\define@boolkey{yrdmcm.cls}[MCM@opt@]{abstract}{}
\define@boolkey{yrdmcm.cls}[MCM@opt@]{sheet}{}
\define@boolkey{yrdmcm.cls}[MCM@opt@]{titleinsheet}{}
\define@boolkey{yrdmcm.cls}[MCM@opt@]{keywordsinsheet}{}
\MCM@opt@sheettrue
\MCM@opt@titlepagetrue
\MCM@opt@titleinsheetfalse
\MCM@opt@keywordsinsheetfalse
\MCM@opt@abstracttrue
\newcommand{\mcmsetup}[1]{\setkeys{MCM}{#1}}
\ProcessOptionsX\relax
\LoadClass[a4paper, cs4size]{ctexart}
\newcommand{\team}{Team \#\ \MCM@opt@tcn}
\RequirePackage{fancyhdr, fancybox}
\RequirePackage{ifthen}
\RequirePackage{lastpage}
\RequirePackage{listings}
 

\setCJKfamilyfont{song}[AutoFakeBold = {2.05}]{SimSun}
% ⛔ 固定中文引号字体：防加粗段引号跟随 \textbf→黑体(SimHei)、开引号字形像后引号。
%   独立引号族 zhquote(宋体)+newunicodechar 锁定，加粗/西文环境字形都开闭分明。
%   ⛔ 用 \setCJKfamilyfont+\CJKfamily 机制(加粗段有效)，不用 \newCJKfontfamily(加粗段失效)。
\setCJKfamilyfont{zhquote}[AutoFakeBold]{SimSun}
\RequirePackage{newunicodechar}
\newunicodechar{“}{{\CJKfamily{zhquote}\char"201C}}
\newunicodechar{”}{{\CJKfamily{zhquote}\char"201D}}
\newunicodechar{‘}{{\CJKfamily{zhquote}\char"2018}}
\newunicodechar{’}{{\CJKfamily{zhquote}\char"2019}}
\newcommand*{\songt}{\CJKfamily{song}} % 宋体
 

\RequirePackage{CJKulem}
% \usepackage{CJKpunct}
% \usepackage{setspace}
\RequirePackage{titlesec}
\RequirePackage{titletoc}
 \usepackage{times}
% \RequirePackage{titletoc}

% \def\breaklong#1{\@tfor\onechar:=#1\do{{\onechar\allowbreak}}} % 英文自动断行
% \makeatother
% 定义字体字号
% =================================================================
\newcommand{\chuhao}{\fontsize{42bp}{\baselineskip}\selectfont} % 初号汉字
\newcommand{\xiaochuhao}{\fontsize{36pt}{\baselineskip}\selectfont} % 小初号汉字
\newcommand{\yihao}{\fontsize{28pt}{\baselineskip}\selectfont} % 一号汉字
\newcommand{\xiaoyi}{\fontsize{24pt}{\baselineskip}\selectfont} % 一号汉字
\newcommand{\erhao}{\fontsize{21pt}{\baselineskip}\selectfont} % 二号汉字
\newcommand{\xiaoerhao}{\fontsize{18pt}{\baselineskip}\selectfont} % 小二号汉字
\newcommand{\sanhao}{\fontsize{15.75pt}{\baselineskip}\selectfont}  % 三号汉字
\newcommand{\xiaosanhao}{\fontsize{15pt}{\baselineskip}\selectfont} % 小三号汉字
\newcommand{\sihao}{\fontsize{14pt}{\baselineskip}\selectfont}  % 四号字体
\newcommand{\xiaosihao}{\fontsize{12pt}{\baselineskip}\selectfont} % 小四号汉字
\newcommand{\wuhao}{\fontsize{10.5pt}{\baselineskip}\selectfont} % 五号汉字
\newcommand{\xiaowuhao}{\fontsize{9pt}{\baselineskip}\selectfont} % 小五号汉字
\newcommand{\liuhao}{\fontsize{7.875pt}{\baselineskip}\selectfont} % 六号汉字
\newcommand{\qihao}{\fontsize{5.25pt}{\baselineskip}\selectfont} % 七号汉字
\newcommand{\song}{\CJKfamily{song}} %宋体
\newcommand{\KAI}{\CJKfamily{kai}} %楷体
\newcommand{\HEI}{\CJKfamily{hei}} %黑体
% \newcommand{\MakeBox}[3][s]
%     {\makebox[#2\ccwd][#1]{\let\CJKglue\hfill #3}}
% \newcommand{\MB}[3][c]
%     {\makebox[#2\ccwd][#1]{#3}}

\RequirePackage[toc, page, title, titletoc, header]{appendix}
\RequirePackage{paralist}
\RequirePackage{amsthm, amsfonts}
\RequirePackage{amsmath, bm}
\RequirePackage{amssymb, mathrsfs}
\RequirePackage{latexsym}
\RequirePackage{longtable, multirow, hhline, tabularx, array}
\RequirePackage{flafter}
\RequirePackage{pifont, calc}
\RequirePackage{colortbl, booktabs}
\RequirePackage{geometry,shadowtext}
\RequirePackage[T1]{fontenc}
\RequirePackage[scaled]{berasans}
\RequirePackage{hyperref}
\geometry{top=25mm,bottom=25mm,left=25mm,headsep=5mm,right=25mm}
\RequirePackage{ifpdf, ifxetex}
\ifpdf
  \RequirePackage{graphicx}
  \RequirePackage{epstopdf}
\else
  \ifxetex
    \RequirePackage{graphicx}
  \else
    \RequirePackage[dvipdfmx]{graphicx}
    \RequirePackage{bmpsize}
  \fi
\fi
\RequirePackage[svgnames]{xcolor}
\ifpdf
  \hypersetup{hidelinks}
\else
  \ifxetex
    \hypersetup{hidelinks}
  \else
    \hypersetup{dvipdfm, hidelinks}
  \fi
\fi
%\geometry{a4paper, margin = 1in}
\pagestyle{fancy}
\fancyhf{}
\cfoot{\xiaowuhao\sffamily \thepage}
\renewcommand{\headrulewidth}{0pt}
%\setlength\parskip{1.5\baselineskip}
\renewcommand\tableofcontents{%
    \centerline{\normalfont\Large\bfseries\sffamily\contentsname
        \@mkboth{%
           \MakeUppercase\contentsname}{\MakeUppercase\contentsname}}%
    \vskip 5ex%
    \@starttoc{toc}%
    }
\setcounter{totalnumber}{4}
\setcounter{topnumber}{2}
\setcounter{bottomnumber}{2}
\renewcommand{\textfraction}{0.15}
\renewcommand{\topfraction}{0.85}
\renewcommand{\bottomfraction}{0.65}
\renewcommand{\floatpagefraction}{0.60}
%\renewcommand{\figurename}{图}
%\renewcommand\tablename{\song\wuhao 表}
\graphicspath{{./}{./img/}{./fig/}{./image/}{./figure/}{./picture/}
            {./imgs/}{./figs/}{./images/}{./figures/}{./pictures/}}
\def\maketitle{%
  \thispagestyle{empty}
  \let\saved@thepage\thepage
  \let\thepage\relax
  \null
  \vspace*{9\baselineskip}
  \begingroup\heiti\zihao{-3}
  报名序号: {{\MCM@opt@tcn}}\\[3\baselineskip]
  
  
  论文题目: \MCM@opt@problem 题  \MCM@opt@timu 
 
 \endgroup
 \newpage
  \makesheet
  \let\thepage\saved@thepage
}
\def\abstractname{摘\quad 要} 
  \newbox\@abstract%
  \setbox\@abstract\hbox{}%
  \long\def\abstract{\bgroup\global\setbox\@abstract\vbox\bgroup\hsize\textwidth}%
  \def\endabstract{\egroup\egroup}
  \def\make@abstract{%
    \begin{center}
     \zihao{-4} \textbf{\abstractname}
    \end{center}
    \usebox\@abstract\par
  }
  
\def\keywordsname{关键词} 
  \newbox\@keywords
  \setbox\@keywords\hbox{}
  \def\keywords{\global\setbox\@keywords\vbox\bgroup\noindent}
  \def\endkeywords{\egroup}%
  \def\make@keywords{%
   \par\zihao{-4}\noindent\textbf{\keywordsname}: \usebox\@keywords\hfill\par
  }
 
 
\newcommand{\problem}[1]{\mcmsetup{problem = #1}}
\def\makesheet{%
  %\pagestyle{empty}%
  \setcounter{page}{1}
  \pagestyle{fancy}
  \begin{center}
    \normalfont\songt \bfseries\zihao{4} \MCM@opt@timu \par
 
  \end{center} 
  \make@abstract
  \make@keywords
 }


% 定理定义引用
% =================================================================
\newtheorem{Theorem}{\HEI 定理}[section]
\newtheorem{Lemma}[Theorem]{\HEI 引理}
\newtheorem{Corollary}[Theorem]{\HEI 推论}
\newtheorem{Proposition}[Theorem]{\HEI 命题i}
\newtheorem{Definition}[Theorem]{\HEI 定义}
\newtheorem{Example}[Theorem]{\HEI 例}
\newtheorem{rmk}{\hskip\parindent\heiti 注}

% 章节设置
% =================================================================
\renewcommand\section{\@startsection{section}{1}{\z@}%
  {5pt\@plus .2ex \@minus -.2ex}%
  {3pt \@plus .2ex}%
  {\centering\rmfamily\zihao{4}\bfseries}}
\renewcommand\subsection{\@startsection{subsection}{2}{\z@}%
  {3pt\@plus -.2ex \@minus -.2ex}%
  {2pt \@plus .2ex}%
  {\rmfamily\zihao{-4}\bfseries}}
\renewcommand\subsubsection{\@startsection{subsubsection}{3}{\z@}%
  {1ex\@plus -1ex \@minus -.2ex}%
  {.5ex \@plus .2ex}%
  {\rmfamily\normalsize\bfseries}}
\renewcommand\paragraph{\@startsection{paragraph}{4}{\z@}%
  {1ex \@plus1ex \@minus.2ex}%
  {-1em}%
  {\rmfamily\normalsize}}

% 图表编号设置
% =================================================================
\renewcommand{\thefigure}{\ifnum \c@section>\z@ \arabic{section}-\fi \@arabic\c@figure}
\renewcommand{\thetable}{\ifnum \c@section>\z@ \arabic{section}-\fi \@arabic\c@table}



% 小节编号设置
% =================================================================
\usepackage{zhnumber} % change section number to chinese
\renewcommand\thesection{\zhnum{section}、\hspace{-.5em}}
\renewcommand\thesubsection{\arabic{section}.\arabic{subsection}}

% 定义新的数学命令
% =================================================================
\providecommand{\dif}{\mathop{}\!\mathrm{d}}
\providecommand{\me}{\mathrm{e}}
\providecommand{\mi}{\mathrm{i}}

% 设置代码抄录
% =================================================================
\definecolor{grey}{rgb}{0.8,0.8,0.8}
\definecolor{darkgreen}{rgb}{0,0.3,0}
\definecolor{darkblue}{rgb}{0,0,0.3}
\def\lstbasicfont{\ttfamily\footnotesize}
\lstset{%
   % numbers=left,
   % numberstyle=\small,%
    showstringspaces=false,
    showspaces=false,%
    tabsize=4,%
    frame=lines,%
    basicstyle={\footnotesize\lstbasicfont},%
    keywordstyle=\color{darkblue}\bfseries,%
    identifierstyle=,%
    commentstyle=\color{darkgreen},%\itshape,%
    stringstyle=\color{black}%
}
\lstloadlanguages{C,C++,Java,Matlab,Mathematica}
\endinput

% End of file neepumcm.cls
% =================================================================