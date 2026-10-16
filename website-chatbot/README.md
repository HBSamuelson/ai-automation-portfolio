# BrightSmile Dental chatbot

A website assistant for a fictional Capitol Hill clinic. It answers from 12 markdown pages, captures a visit request, and can hand the visitor to a person. With no `OPENAI_API_KEY`, it answers by retrieving those pages and quoting the matching sentences. With a key, the same notes are sent to `gpt-4o-mini` and the mock reply is the fallback if that call fails.

## Run

```bash
npm install
npm test
npm run report
npm run dev
```

Open [http://127.0.0.1:43123](http://127.0.0.1:43123).

- `/` is the clinic page with the chat widget
- `/desk` is the front-desk sheet (visit requests and handoffs)
- `/report` reruns the 20-question check
- `/widget` is the panel used by the embed

Saved report: `samples/test-report.md`.

## Embed

```html
<script src="http://127.0.0.1:43123/embed.js" async></script>
```

The script adds a button and an iframe pointed at `/widget`.

## What Bright will not do

Medical advice, diagnosis, and medication questions get a refusal and a path to book or call `(303) 555-0140`. Questions that are not on the clinic pages get a low-confidence reply and an offer to take a message. Talk to a person writes a handoff row. Book a visit writes a lead row. Both are stored in `data/` on this machine, which is gitignored.
