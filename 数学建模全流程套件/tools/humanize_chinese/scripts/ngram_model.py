#!/usr/bin/env python3
"""
Chinese N-gram Language Model for AI Text Detection
Character-level bigram + trigram perplexity, burstiness, and entropy analysis.
Pure Python, no external dependencies.

Key insight: AI-generated Chinese text tends to have:
  - Lower perplexity (more predictable character sequences)
  - Lower burstiness (uniform complexity throughout)
  - More uniform entropy across paragraphs
"""

import json
import os
import re
from math import log2, exp

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FREQ_FILE = os.path.join(SCRIPT_DIR, 'ngram_freq_cn.json')

# ─── Frequency Table Loading ───

_FREQ_CACHE = None

def _load_freq():
    """Load n-gram frequency table (cached)."""
    global _FREQ_CACHE
    if _FREQ_CACHE is not None:
        return _FREQ_CACHE

    if not os.path.exists(FREQ_FILE):
        _FREQ_CACHE = {'unigrams': {}, 'bigrams': {}, 'trigrams': {},
                       'corpus_info': {'total_chars': 1}}
        return _FREQ_CACHE

    with open(FREQ_FILE, 'r', encoding='utf-8') as f:
        _FREQ_CACHE = json.load(f)

    # Convert string counts to int if needed
    for key in ('unigrams', 'bigrams', 'trigrams'):
        table = _FREQ_CACHE.get(key, {})
        _FREQ_CACHE[key] = {k: int(v) for k, v in table.items()}

    return _FREQ_CACHE


def _extract_chinese(text):
    """Extract only Chinese characters from text."""
    return re.findall(r'[\u4e00-\u9fff]', text)


# ─── Core Perplexity Computation ───

def _bigram_log_prob(c1, c2, freq):
    """
    Compute log2 probability of bigram (c1, c2) using add-k smoothing.
    P(c2|c1) ≈ (count(c1c2) + k) / (count(c1) + k * V)
    """
    unigrams = freq['unigrams']
    bigrams = freq['bigrams']
    V = max(len(unigrams), 1000)  # vocabulary size
    k = 0.01  # smoothing factor

    bigram_key = c1 + c2
    bi_count = bigrams.get(bigram_key, 0)
    uni_count = unigrams.get(c1, 0)

    prob = (bi_count + k) / (uni_count + k * V)
    return log2(prob) if prob > 0 else -20.0  # floor for unseen


def _trigram_log_prob(c1, c2, c3, freq):
    """
    Compute log2 probability of trigram using interpolation with bigrams.
    P_interp = lambda * P_tri(c3|c1c2) + (1-lambda) * P_bi(c3|c2)
    """
    bigrams = freq['bigrams']
    trigrams = freq['trigrams']
    V = max(len(freq['unigrams']), 1000)
    k = 0.01
    lam = 0.6  # trigram weight

    # Trigram probability
    tri_key = c1 + c2 + c3
    bi_context_key = c1 + c2
    tri_count = trigrams.get(tri_key, 0)
    bi_context_count = bigrams.get(bi_context_key, 0)
    p_tri = (tri_count + k) / (bi_context_count + k * V)

    # Bigram probability (backoff)
    p_bi_raw = _bigram_log_prob(c2, c3, freq)
    p_bi = 2 ** p_bi_raw  # convert back from log2

    # Interpolation in probability space
    p_interp = lam * p_tri + (1 - lam) * p_bi
    return log2(p_interp) if p_interp > 0 else -20.0


def compute_perplexity(text, window_size=0):
    """
    Compute character-level perplexity of Chinese text using interpolated trigram model.

    Args:
        text: input text string
        window_size: if > 0, compute per-window perplexities for burstiness.
                     0 means compute whole-text perplexity only.

    Returns:
        dict with:
          - perplexity: overall perplexity (float)
          - avg_log_prob: average log2 probability per character
          - window_perplexities: list of per-window perplexities (if window_size > 0)
          - char_count: number of Chinese characters used
    """
    freq = _load_freq()
    chars = _extract_chinese(text)

    if len(chars) < 5:
        return {
            'perplexity': 0.0,
            'avg_log_prob': 0.0,
            'window_perplexities': [],
            'char_count': len(chars),
        }

    # Compute per-character log probabilities using trigram model
    log_probs = []
    for i in range(2, len(chars)):
        lp = _trigram_log_prob(chars[i-2], chars[i-1], chars[i], freq)
        log_probs.append(lp)

    if not log_probs:
        return {
            'perplexity': 0.0,
            'avg_log_prob': 0.0,
            'window_perplexities': [],
            'char_count': len(chars),
        }

    # Overall perplexity: 2^(-avg_log_prob)
    avg_lp = sum(log_probs) / len(log_probs)
    perplexity = 2 ** (-avg_lp)

    # Per-window perplexities
    window_ppls = []
    if window_size > 0 and len(log_probs) >= window_size:
        for start in range(0, len(log_probs) - window_size + 1, window_size // 2):
            end = min(start + window_size, len(log_probs))
            chunk = log_probs[start:end]
            if chunk:
                w_avg = sum(chunk) / len(chunk)
                window_ppls.append(2 ** (-w_avg))

    return {
        'perplexity': perplexity,
        'avg_log_prob': avg_lp,
        'window_perplexities': window_ppls,
        'char_count': len(chars),
    }


# ─── Burstiness ───

def compute_burstiness(text, window_size=50):
    """
    Compute burstiness as coefficient of variation of windowed perplexities.

    Human text: higher burstiness (CV > 0.3, some parts simple, some complex)
    AI text: lower burstiness (CV < 0.2, uniformly smooth)

    Args:
        text: input text
        window_size: character window for perplexity segments

    Returns:
        dict with:
          - burstiness: coefficient of variation (std/mean) of window perplexities
          - mean_ppl: mean of window perplexities
          - std_ppl: standard deviation of window perplexities
          - n_windows: number of windows analyzed
    """
    result = compute_perplexity(text, window_size=window_size)
    ppls = result['window_perplexities']

    if len(ppls) < 3:
        return {
            'burstiness': 0.0,
            'mean_ppl': result['perplexity'],
            'std_ppl': 0.0,
            'n_windows': len(ppls),
        }

    mean_ppl = sum(ppls) / len(ppls)
    if mean_ppl == 0:
        return {
            'burstiness': 0.0,
            'mean_ppl': 0.0,
            'std_ppl': 0.0,
            'n_windows': len(ppls),
        }

    variance = sum((p - mean_ppl) ** 2 for p in ppls) / len(ppls)
    std_ppl = variance ** 0.5
    cv = std_ppl / mean_ppl

    return {
        'burstiness': cv,
        'mean_ppl': mean_ppl,
        'std_ppl': std_ppl,
        'n_windows': len(ppls),
    }


# ─── Paragraph Entropy Uniformity ───

def compute_entropy_uniformity(text):
    """
    Compute entropy of each paragraph and measure how uniform they are.

    AI text: paragraphs have very similar entropy (low CV)
    Human text: entropy varies more between paragraphs

    Returns:
        dict with:
          - entropy_cv: coefficient of variation of per-paragraph entropy
          - paragraph_entropies: list of (paragraph_index, entropy) tuples
          - mean_entropy: mean paragraph entropy
          - n_paragraphs: number of paragraphs analyzed
    """
    # Split into paragraphs (by double newline or single newline with enough content)
    raw_paras = re.split(r'\n\s*\n|\n', text)
    paragraphs = [p.strip() for p in raw_paras
                  if p.strip() and len(_extract_chinese(p.strip())) >= 20]

    if len(paragraphs) < 3:
        return {
            'entropy_cv': 0.0,
            'paragraph_entropies': [],
            'mean_entropy': 0.0,
            'n_paragraphs': len(paragraphs),
        }

    # Compute per-paragraph bigram entropy
    para_entropies = []
    for i, para in enumerate(paragraphs):
        chars = _extract_chinese(para)
        if len(chars) < 10:
            continue

        # Bigram frequency within paragraph
        bigrams = {}
        for j in range(len(chars) - 1):
            key = chars[j] + chars[j+1]
            bigrams[key] = bigrams.get(key, 0) + 1

        total = sum(bigrams.values())
        if total == 0:
            continue

        entropy = 0.0
        for count in bigrams.values():
            p = count / total
            if p > 0:
                entropy -= p * log2(p)

        para_entropies.append((i, entropy))

    if len(para_entropies) < 3:
        return {
            'entropy_cv': 0.0,
            'paragraph_entropies': para_entropies,
            'mean_entropy': 0.0,
            'n_paragraphs': len(para_entropies),
        }

    entropies = [e for _, e in para_entropies]
    mean_ent = sum(entropies) / len(entropies)

    if mean_ent == 0:
        return {
            'entropy_cv': 0.0,
            'paragraph_entropies': para_entropies,
            'mean_entropy': 0.0,
            'n_paragraphs': len(para_entropies),
        }

    variance = sum((e - mean_ent) ** 2 for e in entropies) / len(entropies)
    std_ent = variance ** 0.5
    cv = std_ent / mean_ent

    return {
        'entropy_cv': cv,
        'paragraph_entropies': para_entropies,
        'mean_entropy': mean_ent,
        'n_paragraphs': len(para_entropies),
    }


# ─── Combined Analysis ───

def analyze_text(text):
    """
    Run full statistical analysis on text.

    Returns dict with all metrics and AI likelihood indicators:
      - perplexity: overall perplexity
      - burstiness: CV of windowed perplexity
      - entropy_cv: CV of paragraph entropy
      - indicators: dict of boolean flags for AI-like patterns
    """
    chars = _extract_chinese(text)
    char_count = len(chars)

    if char_count < 30:
        return {
            'perplexity': 0.0,
            'burstiness': 0.0,
            'entropy_cv': 0.0,
            'char_count': char_count,
            'indicators': {
                'low_perplexity': False,
                'low_burstiness': False,
                'uniform_entropy': False,
            },
            'details': {},
        }

    # Perplexity
    ppl_result = compute_perplexity(text, window_size=50)

    # Burstiness
    burst_result = compute_burstiness(text, window_size=50)

    # Entropy uniformity
    ent_result = compute_entropy_uniformity(text)

    # Thresholds — conservative, designed for character-level n-gram model.
    #
    # With a small corpus-based model, perplexity direction depends on text style.
    # We use RELATIVE signals rather than absolute thresholds:
    #   - Perplexity: AI formal text often has moderate-high ppl from this model
    #     (formal vocab not well covered), BUT the KEY signal is the range 100-400
    #     which is typical of formulaic AI text using semi-common formal patterns.
    #   - Burstiness: how much perplexity varies across windows.
    #     Very low values (< 0.12) = uniform complexity = AI-like.
    #     BUT short texts have unreliable burstiness, so require enough windows.
    #   - Entropy CV: how uniform paragraph entropy is.
    #     Very low values (< 0.05) = uniform paragraph structure = AI-like.
    #
    # These are intentionally conservative to avoid false positives.
    # With longer texts (1000+ chars) and better frequency data, accuracy improves.

    ppl = ppl_result['perplexity']
    burst = burst_result['burstiness']
    ent_cv = ent_result['entropy_cv']
    n_windows = burst_result['n_windows']
    n_paras = ent_result['n_paragraphs']

    indicators = {
        # Perplexity in the "formulaic formal" range (100-500) with enough text
        'low_perplexity': 50 < ppl < 500 and char_count >= 200,
        # Very low burstiness with enough data points
        'low_burstiness': burst < 0.12 and n_windows >= 6,
        # Very uniform paragraph entropy with enough paragraphs
        'uniform_entropy': ent_cv < 0.05 and n_paras >= 3,
    }

    return {
        'perplexity': ppl,
        'burstiness': burst,
        'entropy_cv': ent_cv,
        'char_count': char_count,
        'indicators': indicators,
        'details': {
            'perplexity_result': {
                'perplexity': ppl_result['perplexity'],
                'avg_log_prob': ppl_result['avg_log_prob'],
                'n_windows': len(ppl_result['window_perplexities']),
            },
            'burstiness_result': {
                'burstiness': burst_result['burstiness'],
                'mean_ppl': burst_result['mean_ppl'],
                'std_ppl': burst_result['std_ppl'],
                'n_windows': burst_result['n_windows'],
            },
            'entropy_result': {
                'entropy_cv': ent_result['entropy_cv'],
                'mean_entropy': ent_result['mean_entropy'],
                'n_paragraphs': ent_result['n_paragraphs'],
            },
        },
    }


# ─── CLI ───

def main():
    import argparse

    parser = argparse.ArgumentParser(description='中文文本 N-gram 统计分析 — 困惑度/突发度/熵')
    parser.add_argument('file', nargs='?', help='输入文件路径（不指定则从 stdin 读取）')
    parser.add_argument('-j', '--json', action='store_true', help='JSON 输出')
    parser.add_argument('-v', '--verbose', action='store_true', help='详细模式')
    args = parser.parse_args()

    import sys
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                text = f.read()
        except FileNotFoundError:
            print(f'错误: 文件未找到 {args.file}', file=sys.stderr)
            sys.exit(1)
    else:
        text = sys.stdin.read()

    if not text.strip():
        print('错误: 输入为空', file=sys.stderr)
        sys.exit(1)

    result = analyze_text(text)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # Human-readable output
    ppl = result['perplexity']
    burst = result['burstiness']
    ent_cv = result['entropy_cv']
    indicators = result['indicators']

    print(f'字符数: {result["char_count"]}')
    print(f'困惑度 (perplexity): {ppl:.1f}')
    print(f'突发度 (burstiness):  {burst:.3f}')
    print(f'段落熵变异 (entropy CV): {ent_cv:.3f}')
    print()

    print('── AI 特征判断 ──')
    for key, desc in [
        ('low_perplexity', '困惑度异常低（过于流畅/可预测）'),
        ('low_burstiness', '困惑度变化过于均匀（缺少起伏）'),
        ('uniform_entropy', '段落间熵值分布过于均匀'),
    ]:
        flag = '⚠️  是' if indicators[key] else '✅ 否'
        print(f'  {flag} — {desc}')

    if args.verbose and result['details']:
        print()
        print('── 详细数据 ──')
        d = result['details']
        print(f'  平均 log2 概率: {d["perplexity_result"]["avg_log_prob"]:.3f}')
        print(f'  窗口数: {d["burstiness_result"]["n_windows"]}')
        print(f'  窗口平均困惑度: {d["burstiness_result"]["mean_ppl"]:.1f}')
        print(f'  窗口困惑度标准差: {d["burstiness_result"]["std_ppl"]:.1f}')
        print(f'  段落数: {d["entropy_result"]["n_paragraphs"]}')
        print(f'  段落平均熵: {d["entropy_result"]["mean_entropy"]:.3f}')


if __name__ == '__main__':
    main()
