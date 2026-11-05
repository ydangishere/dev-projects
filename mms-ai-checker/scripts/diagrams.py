"""Regenerate exact PNG architecture/UX diagrams with Pillow (optional dev dependency)."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
NAVY, MUTED, LINE = "#0b203c", "#47566b", "#a7b5c5"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def font(size):
    return ImageFont.truetype(FONT, size)


def canvas(title, subtitle, height=1370):
    image = Image.new("RGB", (1600, height), "#f8fafc")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((55, 45, 1545, 155), radius=18, fill=NAVY)
    draw.text((85, 66), title, font=font(33), fill="white")
    draw.text((85, 116), subtitle, font=font(17), fill="#d1dbe7")
    return image, draw


def box(draw, xy, title, lines, fill="white", accent=NAVY):
    x, y, w, h = xy
    draw.rounded_rectangle(
        (x, y, x + w, y + h), radius=15, fill=fill, outline="#ccd5e0", width=2
    )
    draw.rounded_rectangle((x, y, x + 7, y + h), radius=3, fill=accent)
    draw.text((x + 24, y + 18), title, font=font(23), fill=NAVY)
    for i, line in enumerate(lines):
        draw.text((x + 24, y + 57 + 29 * i), line, font=font(18), fill=MUTED)


def arrow(draw, points, label=None):
    draw.line(points, fill=LINE, width=4)
    x, y = points[-1]
    px, py = points[-2]
    if y > py:
        polygon = [(x, y), (x - 9, y - 16), (x + 9, y - 16)]
    elif x > px:
        polygon = [(x, y), (x - 16, y - 9), (x - 16, y + 9)]
    else:
        polygon = [(x, y), (x + 16, y - 9), (x + 16, y + 9)]
    draw.polygon(polygon, fill=LINE)
    if label:
        draw.text(
            (points[0][0] + 12, points[0][1] + 8), label, font=font(15), fill=MUTED
        )


def backend():
    image, d = canvas(
        "BACKEND FLOW | MMS AI Document Checker",
        "Python / FastAPI modular monolith - synthetic MMS data - optional real Gemini API",
    )
    box(
        d,
        (70, 205, 650, 130),
        "1  Employee request + access boundary",
        [
            "Bearer identity -> tenant + role check",
            "Bounded fields, uploads, request bytes, actor rate limit",
        ],
    )
    box(
        d,
        (70, 385, 650, 130),
        "2  Snapshot application + source documents",
        [
            "SQLite fixture repository / uploaded PDF, image or demo TXT",
            "Version, verification status, SHA-256, original source bytes",
        ],
    )
    box(
        d,
        (70, 565, 650, 145),
        "3  OCR / document extraction",
        [
            "Gemini multimodal -> typed JSON facts",
            "Field + value + page + quote + confidence",
            "Demo: deterministic TXT parsing, no AI call",
        ],
    )
    box(
        d,
        (880, 565, 650, 145),
        "4  RAG: retrieve approved policy sections",
        [
            "Local Markdown sections ranked by lexical matching",
            "Tenant + effective date + policy version/hash",
            "Every executed rule is always included",
        ],
    )
    box(
        d,
        (70, 770, 650, 145),
        "5  Deterministic Rule Engine",
        [
            "YAML -> missing / expired / mismatch / verification",
            "Unknown or failed OCR -> manual review finding",
            "Gemini facts always require employee source review",
        ],
    )
    box(
        d,
        (880, 770, 650, 145),
        "6  Gemini explanation / safe fallback",
        [
            "Only immutable findings + policy context",
            "Strict JSON, finding IDs and output screening",
            "Failure -> deterministic explanation; findings unchanged",
        ],
    )
    box(
        d,
        (70, 980, 650, 145),
        "7  Persist check + evidence + audit",
        [
            "Historical source bytes and policy snapshot",
            "GET result / evidence / original; stale-version flag",
            "Checker feedback logged; no model retraining",
        ],
    )
    box(
        d,
        (880, 980, 650, 145),
        "8  MMS review workbench",
        [
            "Result + source page + rule section",
            "Employee inspects source and makes bank decision",
            "No approval endpoint or payment capability",
        ],
    )
    arrow(d, [(395, 335), (395, 385)])
    arrow(d, [(395, 515), (395, 565)])
    arrow(d, [(720, 635), (880, 635)])
    arrow(d, [(1205, 710), (1205, 735), (760, 735), (760, 750), (395, 750), (395, 770)])
    arrow(d, [(720, 840), (880, 840)])
    arrow(d, [(1205, 915), (1205, 940), (760, 940), (760, 960), (395, 960), (395, 980)])
    arrow(d, [(720, 1050), (880, 1050)])
    d.text(
        (75, 1190),
        "Trust boundary: documents and employee questions never control policy, roles or approval.",
        font=font(22),
        fill=NAVY,
    )
    d.text(
        (75, 1235),
        "Runtime: one app container + persistent SQLite volume. Real bank / MMS integration is not connected.",
        font=font(19),
        fill=MUTED,
    )
    image.save(ROOT / "docs/backend_flow.png")


def ux():
    image, d = canvas(
        "EMPLOYEE UX FLOW | PVcomBank Card Center",
        "Feature 1 of 3: Document checking - transaction explanations and guided operations are outside this build",
    )
    box(
        d,
        (70, 215, 650, 140),
        "1  Open an authorized merchant application",
        [
            "Employee signs in using a configured demo token",
            "Select application; inspect current document versions",
            "Maker/checker can check; viewer can only read",
        ],
    )
    box(
        d,
        (880, 215, 650, 140),
        "2  Ask the document assistant",
        [
            'Employee: "What is missing for this application?"',
            'Vietnamese: "Ho so nay con thieu gi de duoc duyet?"',
            "Click Check - see loading and actionable error states",
        ],
    )
    box(
        d,
        (70, 430, 650, 150),
        "3  Read the checking result",
        [
            "Assistant: bank confirmation is missing; ID expired",
            "Current license version has not been verified",
            "Separate blockers from issues needing human review",
        ],
    )
    box(
        d,
        (880, 430, 650, 150),
        "4  Open evidence for each finding",
        [
            "Exact source version + page + excerpt",
            "Applicable policy section and immutable source file",
            "Missing document -> application manifest, no fake page",
        ],
    )
    box(
        d,
        (70, 660, 650, 150),
        "5A  Employee needs a correction",
        [
            "Request correction in the existing bank workflow",
            "Demo: upload replacement document, status = pending",
            "Old check becomes stale; run the check again",
        ],
        fill="#fff8e8",
        accent="#f59f0a",
    )
    box(
        d,
        (880, 660, 650, 150),
        "5B  No issue found in checking scope",
        [
            "Assistant does not claim approval eligibility",
            "Employee still checks originals and bank procedure",
            "OCR facts always remain advisory",
        ],
        fill="#eff5ed",
        accent="#477542",
    )
    box(
        d,
        (70, 900, 650, 150),
        "6  Reviewer gives feedback",
        [
            'Per finding: "Correct", "Incorrect", "Needs review"',
            "Only checker role can submit feedback",
            "Stored in audit log; does not change decision or train AI",
        ],
    )
    box(
        d,
        (880, 900, 650, 150),
        "7  Bank employee decides in MMS",
        [
            "Existing maker-checker approval workflow",
            "Approval is outside this standalone service",
            "No money movement, payout or transaction lookup",
        ],
    )
    arrow(d, [(720, 285), (880, 285)])
    arrow(d, [(1205, 355), (1205, 390), (395, 390), (395, 430)])
    arrow(d, [(720, 500), (880, 500)])
    arrow(d, [(1205, 580), (1205, 620), (395, 620), (395, 660)])
    arrow(d, [(1205, 580), (1205, 660)])
    arrow(d, [(395, 810), (395, 900)])
    arrow(d, [(1205, 810), (1205, 850), (760, 850), (760, 870), (395, 870), (395, 900)])
    arrow(d, [(720, 975), (880, 975)])
    d.text(
        (75, 1140),
        "Conversation is scoped to one selected application; input cannot override banking rules.",
        font=font(22),
        fill=NAVY,
    )
    d.text(
        (75, 1190),
        "Demo cases: missing + expired + unverified / account name mismatch / no issue in scope.",
        font=font(20),
        fill=MUTED,
    )
    image.save(ROOT / "docs/ux_flow.png")


if __name__ == "__main__":
    (ROOT / "docs").mkdir(exist_ok=True)
    backend()
    ux()
