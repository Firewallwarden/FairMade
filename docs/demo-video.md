# FairMade demo video: target 2 minutes 45 seconds

Deliverable status: script and recording instructions prepared; no recording or
YouTube upload is claimed. Channel requested by the owner: **mfranca915**, using
their Google account. Confirm the selected channel inside YouTube Studio rather
than assuming that a matching Google login selects it.

## Prepare actual app footage

Use the final clean integrated build and the integration chat's accepted workflow.
Record a desktop browser at a readable resolution. Prepare separate synthetic
seller/buyer sessions and one in-stock listing. Label synthetic business data and
sandbox transactions visibly in the recording. Have the exact saved analysis,
Quality Lock result and public Passport ready. Warm the model, but record a real
question and answer. Do not substitute a typed answer or fake payment status.

Record actual interactions with your available screen recorder. Use your own
voice and no background music. Close email, notifications, password managers,
developer tools and unrelated tabs. Keep credentials, payment logins and tokens
out of the capture. Trim login entry and long waits; mark cuts or sped-up waits
honestly. Leave time for both real AI and backend-confirmed PayPal checkout.

## Shot list and narration

| Time | Actual screen action | Suggested voiceover |
| --- | --- | --- |
| 0:00-0:15 | Open the real seller product workspace; title overlay: FairMade / synthetic demo data. | "Small makers need to cover their work without cutting quality. Buyers want to understand the price. FairMade connects those needs, from production costs to a PayPal sandbox purchase." |
| 0:15-0:40 | Show sourdough cost inputs and saved deterministic analysis. Change one scenario and show the result. | "This seller records ingredients, labor, packaging and overhead. The engine calculates unit costs, break-even and margin scenarios. These are demo inputs, and the money calculations are deterministic." |
| 0:40-0:58 | Open Quality Lock and one excluded supplier quote. | "A cheaper supplier is not automatically acceptable. Mandatory Quality Locks exclude options that fail the seller's requirements, while source dates and unknowns remain visible." |
| 0:58-1:23 | Ask seller assistant to explain the selected analysis; show real response and short follow-up if time allows. | "Local Qwen3 explains the selected evidence and supports follow-up questions. Exact financial facts stay separate from generated explanation. AI cannot silently change costs, quality requirements or publication." |
| 1:23-1:43 | Show seller disclosure controls, then the buyer's approved Passport. | "The seller chooses what buyers can see. The Fair Price Passport explains approved price and quality information without exposing private recipes or business records." |
| 1:43-2:25 | Buyer purchases the listing through actual sandbox checkout; show backend-confirmed paid order and resulting stock/history. | "Now that understanding becomes a purchase. PayPal is central to the transaction: the backend calculates the order amount and verifies capture before FairMade records payment and updates inventory. This uses the free sandbox, with no real funds." |
| 2:25-2:38 | Show seller order/pickup history or buyer refund-request control. | "Buyer and seller can continue through order messages, pickup and seller-reviewed refund workflows. An approval click alone is never treated as a completed payment." |
| 2:38-2:45 | End on the app with a simple original-text overlay containing the repository URL. | "FairMade: understand the price, protect the quality, and complete the purchase. Source and setup instructions are in the repository." |

If a step fails, fix it or shorten the demonstrated feature set and adjust the
description. Keep meaningful AI and PayPal in the final cut. Do not use historical
backend-only evidence as a replacement for showing the working browser flow.
Export with a hard ceiling below 3:00; target 2:45 including all title/end frames.

## Rights review

Use original UI footage, original captions and your own voice. Retain existing
[asset credits](../frontend/README.md#asset-credits) and bundled font licenses.
The [Unsplash license](https://unsplash.com/license) covers the credited stock
photos, but does not establish permission for unrelated trademarks or people.
Avoid added sponsor logos, third-party clips, music and copyrighted screenshots.
Check any visible provider branding against applicable developer permissions;
do not assume that entering a hackathon grants unrestricted trademark rights.
If uncertain, crop incidental branding or use a permitted view while retaining
actual payment behavior. Review the final video, not just the script.

## YouTube title

FairMade | AI Price Transparency + PayPal Sandbox | Hackathon Demo

## YouTube description

```text
FairMade helps independent sellers understand production costs while giving
buyers seller-approved price and quality explanations before checkout.

This desktop-browser prototype combines local Qwen3 AI with deterministic
pricing, mandatory Quality Locks, Fair Price Passports and PayPal sandbox
checkout. The backend verifies capture before recording an order as paid.

All business examples are synthetic demo data. Payments use PayPal sandbox;
no real funds are transferred. This is a local prototype, not a live marketplace.

Source and complete local setup:
https://github.com/Firewallwarden/FairMade

Runtime AI: Qwen3 8B through Ollama. Receipt scanning, when enabled, uses
Tesseract OCR and reviewed AI drafts. Development assistance included Codex.

Photo and font credits:
https://github.com/Firewallwarden/FairMade/blob/main/frontend/README.md#asset-credits

Prepared for the PayPal AI Hackathon. No sponsorship or endorsement is claimed.
```

Adjust descriptions to match the final video exactly; do not imply receipt
scanning is demonstrated if it is omitted.

## Upload and verify

Follow [YouTube's upload instructions](https://support.google.com/youtube/answer/57407?hl=en):
sign into the owner's Google account, verify the mfranca915 channel, open Studio,
choose Create / Upload videos, and select the final file. Use the title and
description above, accurate audience settings, and **Public** visibility. Wait
for processing and inspect copyright checks. A private or unlisted upload does
not satisfy the event's public-video requirement.

Open the final watch URL signed out, verify playback and total duration, and
paste that URL into Devpost. Also verify repository access signed out. Submit the
Devpost entry before the deadline and retain the confirmation. A channel URL,
local video file or saved draft is not a substitute for the public watch URL.
