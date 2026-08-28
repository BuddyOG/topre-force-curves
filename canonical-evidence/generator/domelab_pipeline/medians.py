"""Two batch-centre conventions. runfilter-v1.1 adopts median_conventional;
median_upper_middle_legacy is retained only for the documented sensitivity comparison."""

def median_conventional(vals):
    s = sorted(vals); n = len(s)
    if n == 0: raise ValueError("empty")
    m = n // 2
    return s[m] if n % 2 else (s[m - 1] + s[m]) / 2.0

def median_upper_middle_legacy(vals):
    s = sorted(vals)
    if not s: raise ValueError("empty")
    return s[len(s) // 2]
