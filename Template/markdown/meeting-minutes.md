---
date: {{date}}
project: {{project}}
version: {{version}}
participants:
  - {{participant}} ({{role}})
transcript: transcripts/{{transcript_file}}
report: reports/drafts/{{date}}-{{slug}}.md
sent: false
---

# Meeting Minutes — {{project}} {{version}} — {{date}}

**Date:** {{date}}
**Project:** {{project}} {{version}}
**Duration:** {{duration}}
**Facilitator:** {{facilitator}}

## Participants

| Name | Role |
|------|------|
| {{name}} | {{role}} |

---

## Agenda

{{agenda_items}}

---

## Summary

{{high_level_summary_2_3_sentences}}

---

## Key Discussions

### {{topic_1}}
{{discussion_summary}}

### {{topic_2}}
{{discussion_summary}}

---

## Decisions Made

| # | Decision | Owner |
|---|----------|-------|
| 1 | {{decision}} | {{owner}} |

---

## Action Items

| # | Action | Owner | Deadline |
|---|--------|-------|----------|
| 1 | {{action}} | {{owner}} | {{deadline}} |

---

## Open Issues / Blockers

- {{issue_or_blocker}}

---

## Next Meeting

**Date:** {{next_meeting_date}}
**Topics:** {{next_topics}}

---

*Generated from transcript: `transcripts/{{transcript_file}}`*
*Report status: DRAFT — not yet sent*
