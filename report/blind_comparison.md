# Blind Review Comparison Report

This report compares model reviews (with and without the Torvalds skill)
to Linus Torvalds' actual reviews on the same patches.

- **Patches evaluated**: 11
- **Models**: glm5.2, gpt-oss-120b, mistral-small-4-119b, qwen3.8-27b
- **Arms**: skill (with Torvalds skill), baseline (no skill)
- **Judge**: glm5.2 (semantic matching, COI: same model used as reviewer in some cells)
- **Ground truth**: 21 Torvalds findings (pilot set)

## Summary Metrics

| Model | Arm | Patches | TP | FP | FN | Precision | Recall | F1 |
|-------|-----|---------|----|----|----|-----------|---------|-----|
| glm5.2 | baseline | 11 | 2 | 30 | 19 | 6.2% | 9.5% | 7.5% |
| glm5.2 | skill | 11 | 2 | 147 | 19 | 1.3% | 9.5% | 2.4% |
| gpt-oss-120b | baseline | 11 | 1 | 34 | 20 | 2.9% | 4.8% | 3.6% |
| gpt-oss-120b | skill | 11 | 1 | 24 | 20 | 4.0% | 4.8% | 4.3% |
| mistral-small-4-119b | baseline | 11 | 2 | 51 | 19 | 3.8% | 9.5% | 5.4% |
| mistral-small-4-119b | skill | 11 | 2 | 75 | 19 | 2.6% | 9.5% | 4.1% |
| qwen3.8-27b | baseline | 11 | 2 | 29 | 19 | 6.5% | 9.5% | 7.7% |
| qwen3.8-27b | skill | 11 | 2 | 29 | 19 | 6.5% | 9.5% | 7.7% |

## Per-Patch Results

### [PATCH v2 1/2] lib/zstd: add fallback aliases for disabled BMI2 variants

Torvalds found **3** issue(s) in this patch.

| Model | Arm | Model findings | TP | FP | FN |
|-------|-----|---------------|----|----|----|
| glm5.2 | baseline | 2 | 1 | 1 | 2 |
| glm5.2 | skill | 4 | 1 | 3 | 2 |
| gpt-oss-120b | baseline | 3 | 0 | 3 | 3 |
| gpt-oss-120b | skill | 0 | 0 | 0 | 3 |
| mistral-small-4-119b | baseline | 4 | 1 | 3 | 2 |
| mistral-small-4-119b | skill | 6 | 1 | 5 | 2 |
| qwen3.8-27b | baseline | 3 | 0 | 3 | 3 |
| qwen3.8-27b | skill | 1 | 1 | 0 | 2 |

### [PATCH hazptr 2/4] compiler.h: Introduce ptr_eq() to preserve address dependency

Torvalds found **2** issue(s) in this patch.

| Model | Arm | Model findings | TP | FP | FN |
|-------|-----|---------------|----|----|----|
| glm5.2 | baseline | 2 | 0 | 2 | 2 |
| glm5.2 | skill | 3 | 0 | 3 | 2 |
| gpt-oss-120b | baseline | 1 | 0 | 1 | 2 |
| gpt-oss-120b | skill | 2 | 0 | 2 | 2 |
| mistral-small-4-119b | baseline | 0 | 0 | 0 | 2 |
| mistral-small-4-119b | skill | 9 | 1 | 8 | 1 |
| qwen3.8-27b | baseline | 0 | 0 | 0 | 2 |
| qwen3.8-27b | skill | 4 | 0 | 4 | 2 |

### [PATCH v4 next 1/9] locking/osq_lock: Add some comments about how it works

Torvalds found **5** issue(s) in this patch.

| Model | Arm | Model findings | TP | FP | FN |
|-------|-----|---------------|----|----|----|
| glm5.2 | baseline | 7 | 0 | 7 | 5 |
| glm5.2 | skill | 4 | 0 | 4 | 5 |
| gpt-oss-120b | baseline | 1 | 0 | 1 | 5 |
| gpt-oss-120b | skill | 4 | 0 | 4 | 5 |
| mistral-small-4-119b | baseline | 6 | 0 | 6 | 5 |
| mistral-small-4-119b | skill | 10 | 0 | 10 | 5 |
| qwen3.8-27b | baseline | 4 | 0 | 4 | 5 |
| qwen3.8-27b | skill | 2 | 0 | 2 | 5 |

### [PATCH] net: qrtr: resend HELLO on MHI resume

Torvalds found **1** issue(s) in this patch.

| Model | Arm | Model findings | TP | FP | FN |
|-------|-----|---------------|----|----|----|
| glm5.2 | baseline | 3 | 0 | 3 | 1 |
| glm5.2 | skill | 4 | 0 | 4 | 1 |
| gpt-oss-120b | baseline | 5 | 0 | 5 | 1 |
| gpt-oss-120b | skill | 4 | 0 | 4 | 1 |
| mistral-small-4-119b | baseline | 5 | 0 | 5 | 1 |
| mistral-small-4-119b | skill | 7 | 0 | 7 | 1 |
| qwen3.8-27b | baseline | 4 | 0 | 4 | 1 |
| qwen3.8-27b | skill | 3 | 0 | 3 | 1 |

### [PATCH v2 01/21] kbuild: do not allocate .modinfo in vmlinux

Torvalds found **1** issue(s) in this patch.

| Model | Arm | Model findings | TP | FP | FN |
|-------|-----|---------------|----|----|----|
| glm5.2 | baseline | 5 | 0 | 5 | 1 |
| glm5.2 | skill | 3 | 0 | 3 | 1 |
| gpt-oss-120b | baseline | 4 | 0 | 4 | 1 |
| gpt-oss-120b | skill | 5 | 0 | 5 | 1 |
| mistral-small-4-119b | baseline | 7 | 0 | 7 | 1 |
| mistral-small-4-119b | skill | 4 | 0 | 4 | 1 |
| qwen3.8-27b | baseline | 3 | 0 | 3 | 1 |
| qwen3.8-27b | skill | 2 | 0 | 2 | 1 |

### [PATCH] docs: remove Assisted-by references

Torvalds found **0** issue(s) in this patch.

| Model | Arm | Model findings | TP | FP | FN |
|-------|-----|---------------|----|----|----|
| glm5.2 | baseline | 0 | 0 | 0 | 0 |
| glm5.2 | skill | 3 | 0 | 3 | 0 |
| gpt-oss-120b | baseline | 2 | 0 | 2 | 0 |
| gpt-oss-120b | skill | 0 | 0 | 0 | 0 |
| mistral-small-4-119b | baseline | 4 | 0 | 4 | 0 |
| mistral-small-4-119b | skill | 7 | 0 | 7 | 0 |
| qwen3.8-27b | baseline | 0 | 0 | 0 | 0 |
| qwen3.8-27b | skill | 0 | 0 | 0 | 0 |

### [PATCH v2 2/2] compiler-gcc: Remove obsolete RELOC_HIDE() macro

Torvalds found **2** issue(s) in this patch.

| Model | Arm | Model findings | TP | FP | FN |
|-------|-----|---------------|----|----|----|
| glm5.2 | baseline | 2 | 1 | 1 | 1 |
| glm5.2 | skill | 3 | 0 | 3 | 2 |
| gpt-oss-120b | baseline | 2 | 1 | 1 | 1 |
| gpt-oss-120b | skill | 2 | 1 | 1 | 1 |
| mistral-small-4-119b | baseline | 4 | 1 | 3 | 1 |
| mistral-small-4-119b | skill | 4 | 0 | 4 | 2 |
| qwen3.8-27b | baseline | 3 | 2 | 1 | 0 |
| qwen3.8-27b | skill | 3 | 1 | 2 | 1 |

### [PATCH v2] tracing: Make is_signed_type() compatible with sparse

Torvalds found **0** issue(s) in this patch.

| Model | Arm | Model findings | TP | FP | FN |
|-------|-----|---------------|----|----|----|
| glm5.2 | baseline | 4 | 0 | 4 | 0 |
| glm5.2 | skill | 4 | 0 | 4 | 0 |
| gpt-oss-120b | baseline | 5 | 0 | 5 | 0 |
| gpt-oss-120b | skill | 1 | 0 | 1 | 0 |
| mistral-small-4-119b | baseline | 5 | 0 | 5 | 0 |
| mistral-small-4-119b | skill | 5 | 0 | 5 | 0 |
| qwen3.8-27b | baseline | 4 | 0 | 4 | 0 |
| qwen3.8-27b | skill | 4 | 0 | 4 | 0 |

### [PATCH net 1/1] net: use random salt for netdev name hash to prevent text base leak

Torvalds found **2** issue(s) in this patch.

| Model | Arm | Model findings | TP | FP | FN |
|-------|-----|---------------|----|----|----|
| glm5.2 | baseline | 0 | 0 | 0 | 2 |
| glm5.2 | skill | 3 | 0 | 3 | 2 |
| gpt-oss-120b | baseline | 1 | 0 | 1 | 2 |
| gpt-oss-120b | skill | 0 | 0 | 0 | 2 |
| mistral-small-4-119b | baseline | 4 | 0 | 4 | 2 |
| mistral-small-4-119b | skill | 5 | 0 | 5 | 2 |
| qwen3.8-27b | baseline | 2 | 0 | 2 | 2 |
| qwen3.8-27b | skill | 3 | 0 | 3 | 2 |

### [PATCH RFC POC 01/50] file: install files on syscall exit

Torvalds found **4** issue(s) in this patch.

| Model | Arm | Model findings | TP | FP | FN |
|-------|-----|---------------|----|----|----|
| glm5.2 | baseline | 3 | 0 | 3 | 4 |
| glm5.2 | skill | 113 | 1 | 112 | 3 |
| gpt-oss-120b | baseline | 6 | 0 | 6 | 4 |
| gpt-oss-120b | skill | 2 | 0 | 2 | 4 |
| mistral-small-4-119b | baseline | 10 | 0 | 10 | 4 |
| mistral-small-4-119b | skill | 15 | 0 | 15 | 4 |
| qwen3.8-27b | baseline | 5 | 0 | 5 | 4 |
| qwen3.8-27b | skill | 7 | 0 | 7 | 4 |

### [PATCH v3 01/20] kbuild: do not allocate .modinfo in vmlinux

Torvalds found **1** issue(s) in this patch.

| Model | Arm | Model findings | TP | FP | FN |
|-------|-----|---------------|----|----|----|
| glm5.2 | baseline | 4 | 0 | 4 | 1 |
| glm5.2 | skill | 5 | 0 | 5 | 1 |
| gpt-oss-120b | baseline | 5 | 0 | 5 | 1 |
| gpt-oss-120b | skill | 5 | 0 | 5 | 1 |
| mistral-small-4-119b | baseline | 4 | 0 | 4 | 1 |
| mistral-small-4-119b | skill | 5 | 0 | 5 | 1 |
| qwen3.8-27b | baseline | 3 | 0 | 3 | 1 |
| qwen3.8-27b | skill | 2 | 0 | 2 | 1 |
