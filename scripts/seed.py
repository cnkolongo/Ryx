"""Script de seed — Données de test pour développement local."""

import asyncio
import httpx

API_BASE = "http://localhost:8000/v1"
AUTH = {"username": "doctor", "password": "doctor123"}


async def get_token() -> str:
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{API_BASE}/auth/token", json=AUTH)
        r.raise_for_status()
        return r.json()["access_token"]


async def seed_patients(token: str) -> list[str]:
    """Créer des patients de test."""
    headers = {"Authorization": f"Bearer {token}"}
    patients = [
        {
            "demographics": {
                "first_name": "Jean-Pierre",
                "last_name": "Mukendi",
                "date_of_birth": "1972-04-15",
                "sex": "M",
                "phone": "+243812345678",
            },
            "identifiers": [{"type": "patient_number", "value": "KASA-001"}],
        },
        {
            "demographics": {
                "first_name": "Marie",
                "last_name": "Kabongo",
                "date_of_birth": "1988-11-20",
                "sex": "F",
                "phone": "+243823456789",
            },
            "identifiers": [{"type": "patient_number", "value": "KASA-002"}],
            "quality_flags": ["approximate_age"],  # âge approximatif
        },
        {
            # Patient avec données fragmentées (cas typique terrain)
            "demographics": None,
            "identifiers": [
                {"type": "name_phonetic", "value": "Mwamba"},
                {"type": "patient_number", "value": "RURAL-042"},
            ],
            "quality_flags": ["no_dob", "no_phone", "incomplete_demographics"],
        },
    ]

    patient_ids = []
    async with httpx.AsyncClient() as client:
        for p in patients:
            try:
                r = await client.post(f"{API_BASE}/patients", json=p, headers=headers)
                r.raise_for_status()
                pid = r.json()["patient_id"]
                patient_ids.append(pid)
                print(f"  ✓ Patient créé: {pid}")
            except httpx.HTTPError as e:
                print(f"  ✗ Erreur: {e}")
    return patient_ids


async def main():
    print("🌱 Seed RYX — Données de test\n")

    try:
        token = await get_token()
        print(f"✓ Auth OK (token obtenu)\n")
    except Exception as e:
        print(f"✗ Impossible de se connecter à l'API: {e}")
        print("  Vérifiez que le service gateway est démarré (make dev)")
        return

    print("📋 Création des patients...")
    patient_ids = await seed_patients(token)

    print(f"\n✅ Seed terminé: {len(patient_ids)} patients créés")
    print("\nPour vérifier: http://localhost:3000/patients")


if __name__ == "__main__":
    asyncio.run(main())
