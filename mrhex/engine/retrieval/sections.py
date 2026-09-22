import re
from mrhex.engine.types import SectionSpan, Section

SECTION_NAMES = {
    "FINDINGS", "IMPRESSION", "CLINICAL_HISTORY", 
    "COMPARISON", "RECOMMENDATION", "TECHNIQUE", 
    "OTHER", "NONE"
}

_HEADER = re.compile(
    r"(?im)(?:^|(?<=[.\n]))\s*(?P<header>findings?|impression|conclusion|clinical\s+history|history|indication|comparison|recommendations?|technique|examination\s+technique|protocol)\s*:\s*"
)

_MAP = {
    "finding": Section.FINDINGS, 
    "findings": Section.FINDINGS,
    "impression": Section.IMPRESSION, 
    "conclusion": Section.IMPRESSION,
    "clinical history": Section.CLINICAL_HISTORY, 
    "history": Section.CLINICAL_HISTORY, 
    "indication": Section.CLINICAL_HISTORY,
    "comparison": Section.COMPARISON, 
    "recommendation": Section.RECOMMENDATION, 
    "recommendations": Section.RECOMMENDATION,
    "technique": Section.TECHNIQUE,
    "examination technique": Section.TECHNIQUE,
    "protocol": Section.TECHNIQUE,
}

def split_report_sections(report: object, source_mode: str = "full_report") -> list[SectionSpan]:
    """Split report text into sections based on headers.
    
    When source_mode == 'findings', headerless text or prefix text before
    embedded headers defaults to FINDINGS provenance.
    When source_mode == 'full_report', defaults to OTHER.
    """
    text = "" if report is None else str(report)
    if not text:
        return []
        
    default_sec = Section.FINDINGS if source_mode == "findings" else Section.OTHER
    matches = list(_HEADER.finditer(text))
    if not matches:
        return [SectionSpan(section=default_sec, start=0, end=len(text), text=text, raw_header="")]
        
    spans: list[SectionSpan] = []
    if matches[0].start() > 0 and text[: matches[0].start()].strip():
        spans.append(SectionSpan(
            section=default_sec, 
            start=0, 
            end=matches[0].start(), 
            text=text[: matches[0].start()],
            raw_header=""
        ))
        
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        raw_header = match.group(0)
        header_key = re.sub(r"\s+", " ", match.group("header").lower())
        
        spans.append(SectionSpan(
            section=_MAP.get(header_key, default_sec),
            start=start,
            end=end,
            text=text[start:end],
            raw_header=raw_header
        ))
        
    return spans

def section_for_offsets(report: str, start: int, end: int, source_mode: str = "full_report") -> Section:
    """Determine which section a character span falls into."""
    if start < 0 or end < start or end > len(report):
        raise ValueError("Evidence offsets outside report")
        
    for span in split_report_sections(report, source_mode=source_mode):
        if start >= span.start and end <= span.end:
            return span.section
            
    return Section.FINDINGS if source_mode == "findings" else Section.OTHER

def all_sections_present(report: str, source_mode: str = "full_report") -> set[Section]:
    """Return all sections found in the report."""
    spans = split_report_sections(report, source_mode=source_mode)
    sections = {span.section for span in spans}
    if source_mode == "findings" and report and str(report).strip():
        sections.add(Section.FINDINGS)
    return sections

