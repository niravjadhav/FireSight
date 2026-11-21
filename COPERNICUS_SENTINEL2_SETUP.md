# Copernicus Sentinel-2 connection (FireSight AI)

## 1. Keep credentials local

The app reads these values from `.env` in the project root:

```env
COPERNICUS_CLIENT_ID=your_client_id
COPERNICUS_CLIENT_SECRET=your_client_secret
```

Copy `.env.example` to `.env`, then add your real values. Do not upload `.env` to GitHub or include it in a ZIP shared with others. The client secret is used only by Python on the Streamlit server; it is never placed in browser JavaScript.

## 2. Install dependencies

From the project root with the virtual environment activated:

```powershell
python -m pip install -r requirements.txt
```

`rasterio` is used to read the multi-band GeoTIFF returned by Sentinel Hub.

## 3. Test credentials and catalogue access

Start the app:

```powershell
python -m streamlit run dashboard/app.py
```

Click **Test Copernicus Connection** in the sidebar. This obtains an OAuth access token and searches the Sentinel-2 L2A catalogue for the selected target area over the last 90 days. It reports authentication and catalogue access separately from image availability.

## 4. Run a fire assessment

Click **Run Intelligence Pipeline**. The automatic post-fire workflow starts only if NASA FIRMS returns a hotspot. It uses the nearest hotspot's coordinates and FIRMS acquisition date, searches for a low-cloud pre-fire scene (up to 90 days before) and post-fire scene (up to 90 days after), requests B04/B08/B12 reflectance, and calculates NDVI, NBR, dNBR, burned area, and a project composite severity score.

If no active FIRMS hotspot exists, if the fire is too recent to have a post-event Sentinel-2 acquisition, or if a suitable image pair cannot be found, the app correctly reports **NOT ASSESSED** with the reason. It does not substitute synthetic imagery or treat a historical catalogue match as a current fire.

## 5. Important interpretation limits

- Sentinel-2 imagery is not a real-time fire alarm. Revisit timing, cloud cover, and product availability can delay a post-fire pair.
- The current automated AOI is an approximately 1 km radius around the nearest FIRMS hotspot, and the pair search uses a 30% cloud-cover ceiling.
- The current dNBR thresholding is an estimate and should be visually validated and calibrated for local vegetation/seasonal conditions before operational use.
- Infrastructure damage remains unavailable because that requires suitable higher-resolution data and a separately validated detection workflow.
- Copernicus Sentinel data attribution should be retained in outputs: "Contains modified Copernicus Sentinel data [year] processed by Sentinel Hub." 
