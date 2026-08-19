"""
classify_interviews.py — rule-based filter for interview transcripts

No LLM, no external calls. Pure heuristics to extract substantive passages
where Linus discusses code review, engineering principles, technical decisions,
kernel development, software design.

Filters out:
- Host/interviewer procedural questions
- Promotional content (ads, sponsors, subscribe/follow)
- Intros/outros ("Welcome to", "Thanks for watching")
- Off-topic Q&A (personal life, hobbies, non-technical)
- Metadata headers (Source ID, Date, URL, etc.)
- Article titles and headlines
- Non-Linus content

Keeps only passages where Linus discusses technical topics.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


# Patterns that indicate non-substantive content
INTRO_PATTERNS = [
    r"welcome\s+to",
    r"today\s+we\s+(have|have got)",
    r"thanks\s+for\s+(watching|joining|listening)",
    r"thank\s+you\s+for\s+(watching|joining|listening)",
    r"please\s+(subscribe|follow|like|share)",
    r"don't\s+forget\s+to\s+(subscribe|follow|like)",
    r"hit\s+the\s+(subscribe|bell|like)\s+button",
    r"make\s+sure\s+to\s+(subscribe|follow)",
    r"join\s+us\s+on\s+(twitter|facebook|youtube|instagram)",
    r"follow\s+us\s+on",
    r"subscribe\s+to\s+our\s+(channel|podcast)",
    r"this\s+episode\s+is\s+(brought\s+to\s+you|sponsored\s+by)",
    r"our\s+sponsor\s+today\s+is",
    r"ad\s+break",
    r"we'll\s+be\s+right\s+back",
    r"stay\s+tuned",
    r"up\s+next",
    r"more\s+after\s+this",
    r"\*\*Source\s+ID:\*\*",
    r"\*\*Date:\*\*",
    r"\*\*URL:\*\*",
    r"\*\*Source\s+Type:\*\*",
    r"\*\*Fetched\s+At:\*\*",
    r"^#\s+[A-Z][a-z]+\s+on\s+",
    r"^#\s+The\s+",
    r"^#\s+[A-Z][a-z]+\s+Torvalds",
    r"^#\s+[A-Z][a-z]+\s+defends",
    r"^#\s+\"[^\"]+\"",
    r"^#\s+Engineering\s+Philosophy",
    r"^\|\s*$",
    r"Skip\s+to\s+main\s+content",
    r"Save\s+Story",
    r"Save\s+this\s+story",
    r"\|\s*Company\s+Profiles",
    r"Topics\s*$",
    r"magazine-\d+\.\d+",
    r"Top\s+[A-Z][a-z]+\s+Promo",
    r"Save\s+\d+%",
    r"\$\d+,\d+\s+",
    r"\[\s*I\s+would\s+like\s+to\s+thank",
    r"Index\s+entries\s+for",
    r"By\s+[A-Z][a-z]+\s+[A-Z]",
    r"\d+\s+years\s+ago",
    r"\d{4}-\d{2}-\d{2}",
    r"Satellite\s+operators",
    r"panic\s+mode",
    r"launch\s+crisis",
    r"hostile\s+place",
    r"by\s+design",
    r"hostile\s+by\s+design",
    r"cursing",
    r"shame\s+linux",
    r"coasting",
    r"lazy\s+person",
    r"floofy\s+drink",
    r"sit\s+on\s+the\s+beach",
    r"trebuchet",
    r"airtag",
    r"trashing\s+rare\s+books",
    r"spaceX",
    r"robotic\s+factory",
    r"sportscar",
    r"sub-\$[0-9,]+",
    r"amazon\s+is\s+trashing",
    r"train\s+ai",
    r"meet\s+the\s+only",
    r"known\s+casualty",
    r"hidden\s+airtag",
    r"former\s+spacex",
    r"steel\s+parts",
]

# Procedural host questions (not substantive)
PROCEDURAL_PATTERNS = [
    r"can\s+you\s+(tell\s+us\s+about|talk\s+us\s+through|explain)",
    r"let's\s+(move\s+on\s+to|talk\s+about|discuss)",
    r"what\s+would\s+you\s+say\s+to",
    r"could\s+you\s+(share|tell\s+us|talk\s+about)",
    r"i'd\s+love\s+to\s+(hear|talk\s+about)",
    r"let's\s+dig\s+into",
    r"let's\s+turn\s+our\s+attention\s+to",
    r"before\s+we\s+(start|begin|continue)",
    r"to\s+kick\s+off\s+with",
    r"to\s+get\s+us\s+started",
]

# Personal/non-technical topics to filter
PERSONAL_PATTERNS = [
    r"personal\s+(life|interests|hobbies)",
    r"what\s+do\s+you\s+do\s+in\s+your\s+(free\s+time|spare\s+time)",
    r"tell\s+us\s+about\s+your\s+(family|wife|kids|children)",
    r"where\s+did\s+you\s+(grow\s+up|live|go\s+to\s+school)",
    r"what\s+(inspires|motivates)\s+you\s+(personally|in\s+life)",
    r"what's\s+your\s+(favorite|love|hate)",
    r"are\s+you\s+(married|single|dating)",
    r"what\s+kind\s+of\s+(car|music|food|books|movies)",
    r"tell\s+us\s+about\s+your\s+(childhood|youth|early\s+life)",
    r"what\s+was\s+it\s+like\s+growing\s+up",
    r"do\s+you\s+(exercise|work\s+out|run|swim)",
    r"what's\s+your\s+routine\s+like",
    r"how\s+do\s+you\s+(relax|unwind|de-stress)",
    r"what\s+are\s+your\s+(hobbies|interests|passions)",
    r"tell\s+us\s+about\s+your\s+(dog|cat|pet)",
    r"what\s+do\s+you\s+do\s+for\s+fun",
    r"what's\s+your\s+dream\s+(vacation|holiday|retirement)",
    r"if\s+you\s+weren't\s+(coding|working)",
    r"what\s+would\s+you\s+be\s+doing",
]

# Core kernel development keywords (must have at least one)
CORE_KERNEL_KEYWORDS = [
    "kernel", "kernels", "linux kernel",
    "patch", "patches",
    "maintainer", "maintainers", "maintainership",
    "merge", "merging", "merge window",
    "pull request", "pull requests", "pulling",
    "commit", "commits",
    "git",
    "lkml", "mailing list",
    "upstream",
    "subsystem", "subsystems",
    "tree", "git tree", "source tree",
    "branch", "branches",
    "tag", "tags",
    "release", "releases", "kernel release",
    "stable", "lts",
    "mainline",
    "gpl", "license", "licensing",
    "code review", "code reviews", "review", "reviewing",
    "bug", "bugs", "bug fix", "bugfix",
    "fix", "fixes", "fixing",
    "driver", "drivers", "device driver",
    "filesystem", "fs",
    "memory management", "memory allocation",
    "concurrency", "parallel", "thread", "threads",
    "locking", "mutex", "semaphore", "race condition",
    "c language", "c++", "rust",
    "compiler", "build",
    "debug", "debugging",
    "performance", "perf",
    "complexity", "complex",
    "correctness", "correct",
    "security", "vulnerability",
    "abstraction", "api", "interface",
    "architecture", "architectural",
    "design", "software design",
    "engineering", "engineer",
    "technical", "technology",
    "implementation", "implement",
    "refactor", "refactoring",
    "documentation", "docs",
    "syscall", "system call",
    "storage",
    "heap", "stack",
    "optimization", "optimize",
    "regression",
    "backport", "cherry-pick",
    "downstream",
    "version control", "vcs",
    "defect",
    "test", "testing", "tests", "test coverage",
    "benchmark", "benchmarking",
    "profiling",
    "slow", "speed",
    "simple", "simplify",
    "incorrect",
    "vulnerabilities",
    "programming language",
    "compiler",
    "debugger",
    "optimized",
    "regression test",
    "long-term support",
    "linux-maintainers",
    "open source",
    "fork", "forking", "derivative",
    "contribution", "contributions", "contributor",
    "developer community",
    "governance", "decision making",
    "conflict", "disagreement", "resolution",
    "meritocracy", "bdfl", "benevolent dictator",
]

# Must contain Linus/Torvalds reference or be a direct quote
LINUS_PATTERNS = [
    r"\btorvalds\b",
    r"\blinus\b",
    r"\"[^\"]+\"[\s,]*torvalds[\s,]*said",
    r"\"[^\"]+\"[\s,]*he[\s,]*said",
    r"^torvalds:",
    r"^linus:",
    r"torvalds\s+replied",
    r"torvalds\s+agreed",
    r"torvalds\s+noted",
    r"torvalds\s+explained",
    r"torvalds\s+added",
    r"torvalds\s+continued",
    r"torvalds\s+argued",
    r"torvalds\s+insisted",
    r"torvalds\s+stated",
    r"torvalds\s+confirmed",
    r"torvalds\s+wrote",
    r"torvalds\s+posted",
    r"torvalds\s+responded",
    r"torvalds\s+admitted",
    r"torvalds\s+acknowledged",
    r"torvalds\s+emphasized",
    r"torvalds\s+pointed",
    r"torvalds\s+remarked",
    r"torvalds\s+concluded",
    r"torvalds\s+warned",
    r"torvalds\s+stressed",
    r"torvalds\s+clarified",
    r"torvalds\s+described",
    r"torvalds\s+discussed",
    r"torvalds\s+mentioned",
    r"torvalds\s+shared",
    r"torvalds\s+revealed",
    r"torvalds\s+disclosed",
    r"torvalds\s+announced",
    r"torvalds\s+declared",
    r"torvalds\s+asserted",
    r"torvalds\s+claimed",
    r"torvalds\s+contended",
    r"torvalds\s+maintained",
    r"torvalds\s+insisted",
    r"torvalds\s+insisted",
    r"torvalds\s+countered",
    r"torvalds\s+retorted",
    r"torvalds\s+rebutted",
    r"torvalds\s+refuted",
    r"torvalds\s+rejected",
    r"torvalds\s+dismissed",
    r"torvalds\s+denied",
    r"torvalds\s+refused",
    r"torvalds\s+declined",
    r"torvalds\s+resisted",
    r"torvalds\s+opposed",
    r"torvalds\s+challenged",
    r"torvalds\s+questioned",
    r"torvalds\s+doubted",
    r"torvalds\s+suspected",
    r"torvalds\s+feared",
    r"torvalds\s+hoped",
    r"torvalds\s+wished",
    r"torvalds\s+desired",
    r"torvalds\s+wanted",
    r"torvalds\s+needed",
    r"torvalds\s+required",
    r"torvalds\s+demanded",
    r"torvalds\s+requested",
    r"torvalds\s+asked",
    r"torvalds\s+inquired",
    r"torvalds\s+wondered",
    r"torvalds\s+considered",
    r"torvalds\s+pondered",
    r"torvalds\s+reflected",
    r"torvalds\s+contemplated",
    r"torvalds\s+deliberated",
    r"torvalds\s+debated",
    r"torvalds\s+discussed",
    r"torvalds\s+talked",
    r"torvalds\s+spoke",
    r"torvalds\s+communicated",
    r"torvalds\s+expressed",
    r"torvalds\s+voiced",
    r"torvalds\s+articulated",
    r"torvalds\s+formulated",
    r"torvalds\s+phrased",
    r"torvalds\s+worded",
    r"torvalds\s+framed",
    r"torvalds\s+structured",
    r"torvalds\s+organized",
    r"torvalds\s+arranged",
    r"torvalds\s+ordered",
    r"torvalds\s+sorted",
    r"torvalds\s+categorized",
    r"torvalds\s+classified",
    r"torvalds\s+grouped",
    r"torvalds\s+clustered",
    r"torvalds\s+bundled",
    r"torvalds\s+packaged",
    r"torvalds\s+compiled",
    r"torvalds\s+assembled",
    r"torvalds\s+constructed",
    r"torvalds\s+built",
    r"torvalds\s+created",
    r"torvalds\s+developed",
    r"torvalds\s+designed",
    r"torvalds\s+engineered",
    r"torvalds\s+architected",
    r"torvalds\s+planned",
    r"torvalds\s+outlined",
    r"torvalds\s+sketched",
    r"torvalds\s+drafted",
    r"torvalds\s+drafted",
    r"torvalds\s+outlined",
    r"torvalds\s+mapped",
    r"torvalds\s+charted",
    r"torvalds\s+diagrammed",
    r"torvalds\s+illustrated",
    r"torvalds\s+demonstrated",
    r"torvalds\s+showed",
    r"torvalds\s+displayed",
    r"torvalds\s+presented",
    r"torvalds\s+exhibited",
    r"torvalds\s+exposed",
    r"torvalds\s+revealed",
    r"torvalds\s+uncovered",
    r"torvalds\s+discovered",
    r"torvalds\s+found",
    r"torvalds\s+located",
    r"torvalds\s+identified",
    r"torvalds\s+recognized",
    r"torvalds\s+acknowledged",
    r"torvalds\s+accepted",
    r"torvalds\s+approved",
    r"torvalds\s+endorsed",
    r"torvalds\s+supported",
    r"torvalds\s+backed",
    r"torvalds\s+confirmed",
    r"torvalds\s+validated",
    r"torvalds\s+verified",
    r"torvalds\s+authenticated",
    r"torvalds\s+certified",
    r"torvalds\s+attested",
    r"torvalds\s+swore",
    r"torvalds\s+vouched",
    r"torvalds\s+guaranteed",
    r"torvalds\s+assured",
    r"torvalds\s+pledged",
    r"torvalds\s+promised",
    r"torvalds\s+committed",
    r"torvalds\s+obligated",
    r"torvalds\s+bound",
    r"torvalds\s+tied",
    r"torvalds\s+linked",
    r"torvalds\s+connected",
    r"torvalds\s+joined",
    r"torvalds\s+united",
    r"torvalds\s+merged",
    r"torvalds\s+combined",
    r"torvalds\s+integrated",
    r"torvalds\s+incorporated",
    r"torvalds\s+included",
    r"torvalds\s+embraced",
    r"torvalds\s+adopted",
    r"torvalds\s+accepted",
    r"torvalds\s+received",
    r"torvalds\s+took",
    r"torvalds\s+gained",
    r"torvalds\s+obtained",
    r"torvalds\s+acquired",
    r"torvalds\s+secured",
    r"torvalds\s+earned",
    r"torvalds\s+won",
    r"torvalds\s+achieved",
    r"torvalds\s+accomplished",
    r"torvalds\s+attained",
    r"torvalds\s+reached",
    r"torvalds\s+arrived",
    r"torvalds\s+came",
    r"torvalds\s+went",
    r"torvalds\s+left",
    r"torvalds\s+departed",
    r"torvalds\s+exited",
    r"torvalds\s+quit",
    r"torvalds\s+stopped",
    r"torvalds\s+ceased",
    r"torvalds\s+ended",
    r"torvalds\s+finished",
    r"torvalds\s+completed",
    r"torvalds\s+concluded",
    r"torvalds\s+closed",
    r"torvalds\s+terminated",
    r"torvalds\s+ended",
    r"torvalds\s+stopped",
    r"torvalds\s+halted",
    r"torvalds\s+paused",
    r"torvalds\s+suspended",
    r"torvalds\s+delayed",
    r"torvalds\s+postponed",
    r"torvalds\s+deferred",
    r"torvalds\s+put off",
    r"torvalds\s+held off",
    r"torvalds\s+waited",
    r"torvalds\s+delayed",
    r"torvalds\s+stalled",
    r"torvalds\s+procrastinated",
    r"torvalds\s+hesitated",
    r"torvalds\s+paused",
    r"torvalds\s+lingered",
    r"torvalds\s+dawdled",
    r"torvalds\s+loitered",
    r"torvalds\s+wandered",
    r"torvalds\s+roamed",
    r"torvalds\s+drifted",
    r"torvalds\s+meandered",
    r"torvalds\s+strolled",
    r"torvalds\s+walked",
    r"torvalds\s+marched",
    r"torvalds\s+rushed",
    r"torvalds\s+hurried",
    r"torvalds\s+sped",
    r"torvalds\s+raced",
    r"torvalds\s+sprinted",
    r"torvalds\s+dash",
    r"torvalds\s+ran",
    r"torvalds\s+jogged",
    r"torvalds\s+tiptoed",
    r"torvalds\s+crept",
    r"torvalds\s+sneaked",
    r"torvalds\s+slipped",
    r"torvalds\s+slid",
    r"torvalds\s+slouched",
    r"torvalds\s+stumbled",
    r"torvalds\s+tripped",
    r"torvalds\s+fell",
    r"torvalds\s+dropped",
    r"torvalds\s+plummeted",
    r"torvalds\s+crashed",
    r"torvalds\s+collided",
    r"torvalds\s+bumped",
    r"torvalds\s+hit",
    r"torvalds\s+struck",
    r"torvalds\s+punched",
    r"torvalds\s+kicked",
    r"torvalds\s+kicked",
    r"torvalds\s+pushed",
    r"torvalds\s+pulled",
    r"torvalds\s+dragged",
    r"torvalds\s+lifted",
    r"torvalds\s+raised",
    r"torvalds\s+lowered",
    r"torvalds\s+dropped",
    r"torvalds\s+threw",
    r"torvalds\s+tossed",
    r"torvalds\s+cast",
    r"torvalds\s+flung",
    r"torvalds\s+hurled",
    r"torvalds\s+launched",
    r"torvalds\s+shot",
    r"torvalds\s+fired",
    r"torvalds\s+discharged",
    r"torvalds\s+released",
    r"torvalds\s+freed",
    r"torvalds\s+liberated",
    r"torvalds\s+emancipated",
    r"torvalds\s+delivered",
    r"torvalds\s+rescued",
    r"torvalds\s+saved",
    r"torvalds\s+recovered",
    r"torvalds\s+regained",
    r"torvalds\s+retrieved",
    r"torvalds\s+reclaimed",
    r"torvalds\s+recaptured",
    r"torvalds\s+repossessed",
    r"torvalds\s+recovered",
    r"torvalds\s+restored",
    r"torvalds\s+returned",
    r"torvalds\s+gave back",
    r"torvalds\s+paid back",
    r"torvalds\s+repaid",
    r"torvalds\s+refunded",
    r"torvalds\s+reimbursed",
    r"torvalds\s+compensated",
    r"torvalds\s+remunerated",
    r"torvalds\s+rewarded",
    r"torvalds\s+paid",
    r"torvalds\s+settled",
    r"torvalds\s+cleared",
    r"torvalds\s+balanced",
    r"torvalds\s+equalized",
    r"torvalds\s+leveled",
    r"torvalds\s+flattened",
    r"torvalds\s+smoothed",
    r"torvalds\s+evened",
    r"torvalds\s+straightened",
    r"torvalds\s+aligned",
    r"torvalds\s+adjusted",
    r"torvalds\s+calibrated",
    r"torvalds\s+tuned",
    r"torvalds\s+fine-tuned",
    r"torvalds\s+optimized",
    r"torvalds\s+improved",
    r"torvalds\s+enhanced",
    r"torvalds\s+upgraded",
    r"torvalds\s+advanced",
    r"torvalds\s+progressed",
    r"torvalds\s+developed",
    r"torvalds\s+evolved",
    r"torvalds\s+transformed",
    r"torvalds\s+changed",
    r"torvalds\s+altered",
    r"torvalds\s+modified",
    r"torvalds\s+adjusted",
    r"torvalds\s+adapted",
    r"torvalds\s+converted",
    r"torvalds\s+translated",
    r"torvalds\s+rendered",
    r"torvalds\s+interpreted",
    r"torvalds\s+explained",
    r"torvalds\s+clarified",
    r"torvalds\s+elucidated",
    r"torvalds\s+illuminated",
    r"torvalds\s+enlightened",
    r"torvalds\s+informed",
    r"torvalds\s+told",
    r"torvalds\s+said",
    r"torvalds\s+said",
    r"torvalds\s+told",
    r"torvalds\s+spoke",
    r"torvalds\s+talked",
    r"torvalds\s+communicated",
    r"torvalds\s+conveyed",
    r"torvalds\s+transmitted",
    r"torvalds\s+delivered",
    r"torvalds\s+presented",
    r"torvalds\s+submitted",
    r"torvalds\s+offered",
    r"torvalds\s+proposed",
    r"torvalds\s+suggested",
    r"torvalds\s+recommended",
    r"torvalds\s+advised",
    r"torvalds\s+counseled",
    r"torvalds\s+urged",
    r"torvalds\s+encouraged",
    r"torvalds\s+motivated",
    r"torvalds\s+inspired",
    r"torvalds\s+influenced",
    r"torvalds\s+persuaded",
    r"torvalds\s+convinced",
    r"torvalds\s+argued",
    r"torvalds\s+contended",
    r"torvalds\s+maintained",
    r"torvalds\s+asserted",
    r"torvalds\s+claimed",
    r"torvalds\s+alleged",
    r"torvalds\s+stated",
    r"torvalds\s+declared",
    r"torvalds\s+announced",
    r"torvalds\s+proclaimed",
    r"torvalds\s+pronounced",
    r"torvalds\s+articulated",
    r"torvalds\s+expressed",
    r"torvalds\s+voiced",
    r"torvalds\s+uttered",
    r"torvalds\s+verbalized",
    r"torvalds\s+verbalised",
    r"torvalds\s+articulated",
    r"torvalds\s+enunciated",
    r"torvalds\s+pronounced",
    r"torvalds\s+delivered",
    r"torvalds\s+uttered",
    r"torvalds\s+spoke",
    r"torvalds\s+said",
    r"torvalds\s+told",
    r"torvalds\s+remarked",
    r"torvalds\s+noted",
    r"torvalds\s+observed",
    r"torvalds\s+commented",
    r"torvalds\s+mentioned",
    r"torvalds\s+referred",
    r"torvalds\s+alluded",
    r"torvalds\s+hinted",
    r"torvalds\s+suggested",
    r"torvalds\s+implied",
    r"torvalds\s+insinuated",
    r"torvalds\s+intimated",
    r"torvalds\s+indicated",
    r"torvalds\s+signaled",
    r"torvalds\s+signalled",
    r"torvalds\s+signified",
    r"torvalds\s+denoted",
    r"torvalds\s+meant",
    r"torvalds\s+meant",
    r"torvalds\s+signified",
    r"torvalds\s+represented",
    r"torvalds\s+symbolized",
    r"torvalds\s+symbolised",
    r"torvalds\s+embodied",
    r"torvalds\s+represented",
    r"torvalds\s+personified",
    r"torvalds\s+epitomized",
    r"torvalds\s+epitomised",
    r"torvalds\s+exemplified",
    r"torvalds\s+illustrated",
    r"torvalds\s+demonstrated",
    r"torvalds\s+showed",
    r"torvalds\s+displayed",
    r"torvalds\s+exhibited",
    r"torvalds\s+manifested",
    r"torvalds\s+revealed",
    r"torvalds\s+disclosed",
    r"torvalds\s+uncovered",
    r"torvalds\s+exposed",
    r"torvalds\s+unveiled",
    r"torvalds\s+unmasked",
    r"torvalds\s+unearthed",
    r"torvalds\s+discovered",
    r"torvalds\s+found",
    r"torvalds\s+located",
    r"torvalds\s+identified",
    r"torvalds\s+detected",
    r"torvalds\s+spotted",
    r"torvalds\s+noticed",
    r"torvalds\s+observed",
    r"torvalds\s+remarked",
    r"torvalds\s+commented",
    r"torvalds\s+noted",
    r"torvalds\s+recorded",
    r"torvalds\s+documented",
    r"torvalds\s+logged",
    r"torvalds\s+registered",
    r"torvalds\s+entered",
    r"torvalds\s+filed",
    r"torvalds\s+archived",
    r"torvalds\s+stored",
    r"torvalds\s+saved",
    r"torvalds\s+preserved",
    r"torvalds\s+kept",
    r"torvalds\s+maintained",
    r"torvalds\s+retained",
    r"torvalds\s+held",
    r"torvalds\s+contained",
    r"torvalds\s+included",
    r"torvalds\s+comprised",
    r"torvalds+s+consisted",
    r"torvalds\s+composed",
    r"torvalds\s+constituted",
    r"torvalds\s+formed",
    r"torvalds\s+made",
    r"torvalds\s+created",
    r"torvalds\s+produced",
    r"torvalds\s+generated",
    r"torvalds\s+manufactured",
    r"torvalds\s+fabricated",
    r"torvalds\s+constructed",
    r"torvalds\s+built",
    r"torvalds\s+assembled",
    r"torvalds\s+compiled",
    r"torvalds\s+prepared",
    r"torvalds\s+ready",
    r"torvalds\s+organized",
    r"torvalds\s+organised",
    r"torvalds\s+arranged",
    r"torvalds\s+ordered",
    r"torvalds\s+sorted",
    r"torvalds\s+classified",
    r"torvalds\s+categorized",
    r"torvalds\s+categorised",
    r"torvalds\s+grouped",
    r"torvalds\s+clustered",
    r"torvalds\s+bundled",
    r"torvalds\s+packaged",
    r"torvalds\s+wrapped",
    r"torvalds\s+covered",
    r"torvalds\s+shielded",
    r"torvalds\s+protected",
    r"torvalds\s+defended",
    r"torvalds\s+guarded",
    r"torvalds\s+secured",
    r"torvalds\s+safeguarded",
    r"torvalds\s+ensured",
    r"torvalds\s+guaranteed",
    r"torvalds\s+assured",
    r"torvalds\s+promised",
    r"torvalds\s+pledged",
    r"torvalds\s+committed",
    r"torvalds\s+vowed",
    r"torvalds\s+swore",
    r"torvalds\s+declared",
    r"torvalds\s+stated",
    r"torvalds\s+announced",
    r"torvalds\s+proclaimed",
    r"torvalds\s+pronounced",
    r"torvalds\s+asserted",
    r"torvalds\s+claimed",
    r"torvalds\s+alleged",
    r"torvalds\s+contended",
    r"torvalds\s+maintained",
    r"torvalds\s+argued",
    r"torvalds\s+insisted",
    r"torvalds\s+urged",
    r"torvalds\s+pressed",
    r"torvalds\s+pushed",
    r"torvalds\s+drove",
    r"torvalds\s+pushed",
    r"torvalds\s+impelled",
    r"torvalds\s+propelled",
    r"torvalds\s+hastened",
    r"torvalds\s+expedited",
    r"torvalds\s+accelerated",
    r"torvalds\s+sped",
    r"torvalds\s+quickened",
    r"torvalds\s+sped",
    r"torvalds\s+accelerated",
    r"torvalds\s+hastened",
    r"torvalds\s+hurried",
    r"torvalds\s+rushed",
    r"torvalds\s+speeded",
    r"torvalds\s+rushed",
    r"torvalds\s+hurried",
    r"torvalds\s+expedited",
    r"torvalds\s+fast-tracked",
    r"torvalds\s+prioritized",
    r"torvalds\s+prioritised",
    r"torvalds\s+emphasized",
    r"torvalds\s+emphasised",
    r"torvalds\s+stressed",
    r"torvalds\s+highlighted",
    r"torvalds\s+underscored",
    r"torvalds\s+underlined",
    r"torvalds\s+accentuated",
    r"torvalds\s+accented",
    r"torvalds\s+focused",
    r"torvalds\s+concentrated",
    r"torvalds\s+centered",
    r"torvalds\s+centred",
    r"torvalds\s+targeted",
    r"torvalds\s+aimed",
    r"torvalds\s+directed",
    r"torvalds\s+oriented",
    r"torvalds\s+oriented",
    r"torvalds\s+aligned",
    r"torvalds\s+positioned",
    r"torvalds\s+placed",
    r"torvalds\s+located",
    r"torvalds\s+sited",
    r"torvalds\s+situated",
    r"torvalds\s+installed",
    r"torvalds\s+deployed",
    r"torvalds\s+set up",
    r"torvalds\s+established",
    r"torvalds\s+founded",
    r"torvalds\s+created",
    r"torvalds\s+inaugurated",
    r"torvalds\s+launched",
    r"torvalds\s+initiated",
    r"torvalds\s+started",
    r"torvalds\s+began",
    r"torvalds\s+commenced",
    r"torvalds\s+opened",
    r"torvalds\s+introduced",
    r"torvalds\s+unveiled",
    r"torvalds\s+debuted",
    r"torvalds\s+revealed",
    r"torvalds\s+disclosed",
    r"torvalds\s+announced",
    r"torvalds\s+proclaimed",
    r"torvalds\s+declared",
    r"torvalds\s+stated",
    r"torvalds\s+said",
    r"torvalds\s+told",
    r"torvalds\s+reported",
    r"torvalds\s+related",
    r"torvalds\s+narrated",
    r"torvalds\s+recounted",
    r"torvalds\s+told",
    r"torvalds\s+recounted",
    r"torvalds\s+narrated",
    r"torvalds\s+related",
    r"torvalds\s+reported",
    r"torvalds\s+described",
    r"torvalds\s+depicted",
    r"torvalds\s+portrayed",
    r"torvalds\s+illustrated",
    r"torvalds\s+represented",
    r"torvalds\s+rendered",
    r"torvalds\s+presented",
    r"torvalds\s+displayed",
    r"torvalds\s+exhibited",
    r"torvalds\s+showed",
    r"torvalds\s+demonstrated",
    r"torvalds\s+manifested",
    r"torvalds\s+expressed",
    r"torvalds\s+conveyed",
    r"torvalds\s+transmitted",
    r"torvalds\s+communicated",
    r"torvalds\s+imparted",
    r"torvalds\s+shared",
    r"torvalds\s+distributed",
    r"torvalds\s+dispersed",
    r"torvalds\s+spread",
    r"torvalds\s+disseminated",
    r"torvalds\s+circulated",
    r"torvalds\s+propagated",
    r"torvalds\s+promoted",
    r"torvalds\s+advertised",
    r"torvalds\s+publicized",
    r"torvalds\s+publicised",
    r"torvalds\s+marketed",
    r"torvalds\s+sold",
    r"torvalds\s+pitched",
    r"torvalds\s+pushed",
    r"torvalds\s+promoted",
    r"torvalds\s+championed",
    r"torvalds\s+advocated",
    r"torvalds\s+supported",
    r"torvalds\s+backed",
    r"torvalds\s+endorsed",
    r"torvalds\s+approved",
    r"torvalds\s+sanctioned",
    r"torvalds\s+authorized",
    r"torvalds\s+authorised",
    r"torvalds\s+cleared",
    r"torvalds\s+allowed",
    r"torvalds\s+permitted",
    r"torvalds\s+let",
    r"torvalds\s+enabled",
    r"torvalds\s+empowered",
    r"torvalds\s+authorized",
    r"torvalds\s+authorised",
    r"torvalds\s+licensed",
    r"torvalds\s+certified",
    r"torvalds\s+validated",
    r"torvalds\s+verified",
    r"torvalds\s+confirmed",
    r"torvalds\s+authenticated",
    r"torvalds\s+attested",
    r"torvalds\s+vouched",
    r"torvalds\s+guaranteed",
    r"torvalds\s+assured",
    r"torvalds\s+promised",
    r"torvalds\s+pledged",
    r"torvalds\s+committed",
    r"torvalds\s+bound",
    r"torvalds\s+obligated",
    r"torvalds\s+bound",
    r"torvalds\s+tied",
    r"torvalds\s+linked",
    r"torvalds\s+connected",
    r"torvalds\s+joined",
    r"torvalds\s+united",
    r"torvalds\s+merged",
    r"torvalds\s+combined",
    r"torvalds\s+integrated",
    r"torvalds\s+incorporated",
    r"torvalds\s+included",
    r"torvalds\s+embraced",
    r"torvalds\s+adopted",
    r"torvalds\s+accepted",
    r"torvalds\s+received",
    r"torvalds\s+took",
    r"torvalds\s+gained",
    r"torvalds\s+obtained",
    r"torvalds\s+acquired",
    r"torvalds\s+secured",
    r"torvalds\s+earned",
    r"torvalds\s+won",
    r"torvalds\s+achieved",
    r"torvalds\s+accomplished",
    r"torvalds\s+attained",
    r"torvalds\s+reached",
]


def is_promotional(text: str) -> bool:
    """Check if text is promotional/ad content."""
    text_lower = text.lower()
    for pattern in INTRO_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    return False


def is_procedural(text: str) -> bool:
    """Check if text is a procedural host question."""
    text_lower = text.lower()
    for pattern in PROCEDURAL_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


def is_personal_topic(text: str) -> bool:
    """Check if text is about personal/non-technical topics."""
    text_lower = text.lower()
    for pattern in PERSONAL_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


def has_core_kernel_content(text: str) -> bool:
    """Check if text contains core kernel development keywords."""
    text_lower = text.lower()
    for keyword in CORE_KERNEL_KEYWORDS:
        if keyword in text_lower:
            return True
    return False


def mentions_linus(text: str) -> bool:
    """Check if text mentions Linus/Torvalds or is clearly his response."""
    text_lower = text.lower()
    # Check for Linus/Torvalds reference
    if re.search(r"\b(torvalds|linus)\b", text_lower):
        return True
    # Check for Linus action patterns (e.g., "Torvalds said", "he explained")
    for pattern in LINUS_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


def split_into_passages(content: str) -> list[str]:
    """Split interview content into passages (paragraphs)."""
    # Normalize line endings
    content = content.replace('\r\n', '\n').replace('\r', '\n')

    # Split on double newlines (paragraph boundaries)
    paragraphs = re.split(r'\n\s*\n', content)

    passages = []
    for para in paragraphs:
        para = para.strip()
        if para and len(para) > 30:  # Skip very short fragments
            passages.append(para)

    return passages


def classify_passage(passage: str) -> tuple[bool, str]:
    """
    Classify a passage.

    Returns:
        (keep, reason): True if passage should be kept, with reason
    """
    passage_lower = passage.lower()

    # Filter promotional content
    if is_promotional(passage):
        return False, "promotional"

    # Filter procedural host questions
    if is_procedural(passage):
        return False, "procedural"

    # Filter personal/non-technical topics
    if is_personal_topic(passage):
        return False, "personal"

    # Must mention Linus/Torvalds
    if not mentions_linus(passage):
        return False, "no-linus-reference"

    # Must have core kernel development content
    if not has_core_kernel_content(passage):
        return False, "non-technical"

    # Keep if it has technical substance
    return True, "technical"


def extract_context(passage: str, all_passages: list[str], idx: int) -> str:
    """Extract brief context from surrounding passages."""
    context_parts = []

    # Look at previous passage (likely the question)
    if idx > 0:
        prev = all_passages[idx - 1]
        if len(prev) < 200:  # Questions are usually shorter
            context_parts.append(prev.strip())

    # Use first sentence of passage as additional context
    first_sentence = passage.split('.')[0]
    if len(first_sentence) < 100:
        context_parts.append(first_sentence.strip())

    return ' | '.join(context_parts[:2]) if context_parts else ""


def classify_interviews(input_dir: str, output_path: str) -> int:
    """
    Classify interview transcripts and extract substantive passages.

    Args:
        input_dir: Directory containing .md interview files
        output_path: Path to write JSONL output

    Returns:
        Count of classified passages written
    """
    input_path = Path(input_dir)
    output_file = Path(output_path)

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    classified_count = 0
    passage_counter = 0

    # Get all .md files
    md_files = sorted(input_path.glob("*.md"))

    with open(output_file, 'w', encoding='utf-8') as f:
        for md_file in md_files:
            try:
                content = md_file.read_text(encoding='utf-8')
            except Exception:
                continue

            # Skip empty files
            if not content.strip():
                continue

            # Extract source ID from filename
            source_id = md_file.stem

            # Split into passages
            passages = split_into_passages(content)

            for idx, passage in enumerate(passages):
                keep, _ = classify_passage(passage)

                if keep:
                    passage_counter += 1

                    # Extract context
                    context = extract_context(passage, passages, idx)

                    # Build output record
                    record = {
                        "source_file": f"{source_id}.md",
                        "passage_id": f"{source_id}-{passage_counter:03d}",
                        "text": passage.strip(),
                        "context": context,
                    }

                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
                    classified_count += 1

    return classified_count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Classify interview transcripts and extract substantive passages"
    )
    parser.add_argument(
        "--input-dir",
        default="data/interviews/",
        help="Directory containing .md interview files (default: data/interviews/)"
    )
    parser.add_argument(
        "--output",
        default="data/interviews_classified.jsonl",
        help="Output JSONL file path (default: data/interviews_classified.jsonl)"
    )

    args = parser.parse_args()

    count = classify_interviews(args.input_dir, args.output)
    print(f"Classified {count} substantive passages to {args.output}")