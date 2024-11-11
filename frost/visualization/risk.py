# CELL 8: Detaljert analyse og visualisering
try:
    # 1. Først kjør analysen og lagre resultatene
    print("Starter analyse...")
    results = run_snow_analysis()

    if results is None:
        raise ValueError("Analysen returnerte ingen resultater")

    # 2. Skriv ut parametre
    params = RoadConditionParameters()
    print("\n=== PARAMETRE FOR GLATT VEI ===")
    print("\nTemperaturgrenser:")
    for zone, (min_temp, max_temp) in params.TEMP_ZONES.items():
        print(f"{zone}: {min_temp}°C til {max_temp}°C")

    print("\nNedbørsgrenser:")
    for intensity, value in params.PRECIP_INTENSITY.items():
        print(f"{intensity}: {value} mm")

    print("\nKritiske terskelverdier:")
    for param, value in params.SLIPPERY_THRESHOLDS.items():
        print(f"{param}: {value}")

    # 3. Verifiser at vi har risk_df
    if "risk_df" not in results:
        raise ValueError("Mangler risk_df i resultatene")

    risk_df = results["risk_df"]
    print("\n=== ANALYSERESULTATER ===")
    print(f"Antall datapunkter analysert: {len(risk_df)}")
    print(f"Tidsperiode: {risk_df.index.min()} til {risk_df.index.max()}")
    print(f"Antall timer med høy risiko (>0.7): {(risk_df['risk'] > 0.7).sum()}")

    # Resten av koden kommer her hvis vi får dette til å kjøre...

except Exception as e:
    print(f"Feil under analyse: {e}")
    print("\nDetaljer om results:")
    if "results" in locals():
        print(
            "Tilgjengelige nøkler i results:",
            results.keys() if isinstance(results, dict) else "Results er ikke en dict",
        )