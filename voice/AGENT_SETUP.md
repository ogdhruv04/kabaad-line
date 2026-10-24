# ElevenLabs Agent setup (~15 min)

Do this in the ElevenLabs dashboard → **Agents** → Create agent (blank). Then put its ID in `web/.env` as `VITE_ELEVENLABS_AGENT_ID`.

## 1. Basics
- **Language:** Hindi (add English as an additional language so Hinglish works).
- **Voice:** pick a natural Hindi voice from the library. Use the same voice ID as `ELEVENLABS_VOICE_ID` for briefings so it feels like one product.
- **First message:** `नमस्ते {{collector_name}} जी! कौन सा डस्टबिन भरा है, या आज कितना कबाड़ उठाया?`
- **System prompt:** paste `agent_prompt.md`.
- **Dynamic variables:** `collector_name` (the web page passes it in automatically).

## 2. Server tools (Tools → Add tool → Webhook)
For every tool: Method **POST**, header **`X-Tool-Secret: <same value as TOOL_SHARED_SECRET>`**, body type JSON.
Base URL = your backend: `https://<kabaad-api>.onrender.com` (locally, expose port 8000 with `ngrok http 8000`).

### `report_bin_status` → `POST {BASE}/tools/report_bin_status`
Description: *Log how full a bin is or that it is overflowing. Use whenever the caller mentions a bin, dustbin, kooda or a place that is full.*
| param | type | required | description |
|---|---|---|---|
| location_name | string | yes | Place the caller mentioned, exactly as they said it (Hindi or English). |
| fill_level | string | yes | Their words for how full: "overflowing", "full", "almost full", "half", "empty", or a percent. |
| waste_type | string | no | What kind of waste, if mentioned. |
| note | string | no | Anything else they said. |
| reporter_name | string | no | Use `{{collector_name}}`. |

### `log_collection` → `POST {BASE}/tools/log_collection`
Description: *Log material the collector picked up, with weight in kg.*
| param | type | required | description |
|---|---|---|---|
| material | string | yes | gatta/cardboard, bottle/PET, plastic, loha/metal, e-waste, kaanch/glass, panni/MLP, organic. |
| kg | number | yes | Weight in kilograms. Ask if not given. |
| location_name | string | no | Where it was collected. |
| collector_name | string | yes | Use `{{collector_name}}`. |

### `get_my_route` → `POST {BASE}/tools/get_my_route`
Description: *Get the caller's planned stops for tomorrow, in order.*
| param | type | required | description |
|---|---|---|---|
| collector_name | string | yes | Use `{{collector_name}}`. |

## 3. Test before wiring the UI
Use the dashboard's test call. Say: "राजेंद्र भवन के पीछे वाला डस्टबिन भर गया है" → the dashboard live feed should show it within 5 seconds.

## 4. Stretch: real phone number
ElevenLabs supports Twilio numbers for inbound/outbound calls. Getting an Indian number is slow (regulatory docs), so for the demo stick to the web widget and mention the phone line as the deployment path in your pitch.
