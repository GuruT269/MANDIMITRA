# MandiMitra — 2-minute judge demo

**Before you go on stage**
1. `./run.sh` (or `uvicorn app.main:app --port 8077`) at least 30 s early; check `http://localhost:8077/health` shows `"done": true` (4 demo farms pre-warmed → every click loads in < 1 s).
2. Optional: set `PUBLIC_BASE_URL` to your public/ngrok URL so judges can scan the passport QR on their phones.
3. Open `http://localhost:8077/?lat=12.50&lon=76.85&rad=100&auto=1` in a full-screen browser; keep phone volume up for the Kannada voice.
4. Backup: screenshots in `demo_shots/judge_*.png` if Wi-Fi dies.

## Flow (≈ 2:00)

| Time | Show | Say |
|---|---|---|
| 0:00–0:15 | Header + "Why we're different" strip | "Karnataka has ~80 lakh farmers, most with under 5 acres. Existing agri-apps sell to agribusinesses or need a subscription. MandiMitra is free, Kannada-first, and works from just a lat/long." |
| 0:15–0:45 | **Field** tab, Mandya preset. Point at the LIVE satellite card (date + scene ID), then the Health Score ring | "This is Sentinel-2 imagery of *this* 100 m plot from 13 Nov — the scene ID is clickable, it's not a stock picture. We turn it into one number: Farm Health Score 93/100, and we explain why — vigour, chlorophyll, water, weather risk." |
| 0:45–1:05 | Action card → press **🔊 ಕನ್ನಡ**; toggle **ಕನ್ನಡ** in header | "Every morning the farmer gets three actions in Kannada, read aloud: irrigate ~39 mm, best spray window 1–6 pm today, organic option for any pest risk. No literacy needed." |
| 1:05–1:25 | Crop estimate card → **Sell this crop** → **Where to Sell** tab | "Satellite tells us the crop; Agmarknet tells us prices in 18+ mandis. We rank by *money in hand* after transport, APMC fees, commission, hamali and spoilage — the nearest mandi is often not the best." |
| 1:25–1:50 | **Quality Passport** tab → open `/passport/mandya-demo`, show QR | "This is our unique piece: a Farm Quality Passport. Satellite proof the crop was growing, a 12-month health trend, and the farmer's own input log with bill photos. A buyer scans the QR and can pay a premium for low-chemical produce. Honest labels: inputs are self-declared." |
| 1:50–2:00 | **Advisor** tab → schemes check; type a new lat/long (cold load ≈ 5 s) | "Plus scheme eligibility — PM-KISAN, PMFBY, KCC — with official links. Any farm in India, live, in about 5 seconds. All on free open data: ESA, Open-Meteo, NASA, Agmarknet, OpenStreetMap." |

## Talking points if judges ask
* **Data is real**: Sentinel-2 L2A via Microsoft Planetary Computer, cloud-masked (SCL); Open-Meteo forecast + soil moisture; NASA POWER climate; ISRIC SoilGrids; ESA WorldCover; Agmarknet prices via a keyless mirror (prices ~1 day old). Every card shows its source and date.
* **Cost**: ₹0 per farmer — no paid API keys; optional LLM only rewrites text.
* **Speed**: parallel calls + progressive cards + server cache. Pre-warmed: 0.1 s; brand-new farm: first data 0.1 s, full dashboard 5.4 s.
* **Honesty**: health score is rule-based and explained; crop ID is heuristic; schemes are indicative; organic claims are self-declared with bills, never "certified".
* **Next steps**: WhatsApp/IVR bot, FPO bulk view, Raitha Samparka Kendra partnership, native-speaker Kannada review, lab soil-card upload.

## How we differ (based on public product descriptions — verify before quoting on stage)

| | MandiMitra | Farmonaut | CropIn | Fasal | Plantix | AgriBazaar | e-NAM | Kisan Suvidha |
|---|---|---|---|---|---|---|---|---|
| Free for an individual farmer | ✅ fully, no login | Paid plans | Enterprise / agribusiness | Paid + IoT hardware | ✅ | Trading platform | ✅ (govt) | ✅ (govt) |
| Live satellite view of *your* plot from a lat/long | ✅ | ✅ | ✅ | Sensor-based | ❌ (photo diagnosis) | ❌ | ❌ | ❌ |
| One explained 0–100 health score | ✅ | Indices | Indices/analytics | Sensor dashboard | ❌ | ❌ | ❌ | ❌ |
| Net-price mandi ranking (after transport, fees, spoilage) | ✅ | ❌ | ❌ | ❌ | ❌ | Marketplace prices | Prices & trading | Prices only |
| Crop → best mandi in one click | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Buyer-facing Quality Passport + QR (satellite + input log) | ✅ | ❌ | Traceability for enterprises | ❌ | ❌ | ❌ | ❌ | ❌ |
| Kannada voice daily action card | ✅ | Partial | ❌ | Partial | Multilingual | ❌ | Multilingual UI | Multilingual |
| Spray window + pest risk from weather | ✅ | Partial | ✅ | ✅ | Pest diagnosis | ❌ | ❌ | Weather info |
| Govt scheme quick-check | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Partial |

**One-liner**: *"Others give a farmer data. MandiMitra gives a small farmer one score, three actions in Kannada, the best mandi by money in hand, and a passport that proves his crop's quality — free."*
