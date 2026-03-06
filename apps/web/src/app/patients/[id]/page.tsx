"use client";

import { use } from "react";
import Link from "next/link";
import { usePatient, usePatientTimeline } from "@/hooks/usePatients";
import { EvidenceRefBadge } from "@/components/evidence/EvidenceRefBadge";
import type { Claim, EvidenceRef } from "@/types";

export default function PatientDossierPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: patient, isLoading, isError } = usePatient(id);
  const { data: timeline } = usePatientTimeline(id);

  if (isLoading) {
    return (
      <div className="p-8 text-center text-sm text-gray-400">
        Chargement du dossier...
      </div>
    );
  }

  if (isError || !patient) {
    return (
      <div className="p-8 text-center">
        <p className="text-red-500 text-sm">Patient introuvable</p>
        <Link href="/patients" className="text-blue-600 text-sm mt-2 inline-block">
          ← Retour à la liste
        </Link>
      </div>
    );
  }

  const d = patient.demographics ?? {};
  const encounters = timeline?.encounters ?? [];
  const recentClaims: Claim[] = timeline?.recent_claims ?? [];

  return (
    <main className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <Link href="/patients" className="text-sm text-gray-400 hover:text-gray-600">
          ← Patients
        </Link>
        <div className="flex items-center justify-between mt-2">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {d.last_name} {d.first_name}
            </h1>
            <p className="text-sm text-gray-500 mt-0.5 font-mono">
              ID: {patient.patient_id}
            </p>
          </div>
          {patient.quality_flags?.length > 0 && (
            <div className="flex gap-1">
              {patient.quality_flags.map((flag) => (
                <span
                  key={flag}
                  className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full"
                >
                  {flag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column — Demographics */}
        <div className="space-y-4">
          <InfoCard title="Informations patient">
            <InfoRow label="Nom" value={d.last_name} />
            <InfoRow label="Prénom" value={d.first_name} />
            <InfoRow
              label="Date de naissance"
              value={
                d.date_of_birth
                  ? new Date(d.date_of_birth).toLocaleDateString("fr-CD")
                  : undefined
              }
            />
            <InfoRow label="Sexe" value={d.sex} />
            <InfoRow label="Téléphone" value={d.phone} />
            <InfoRow label="Adresse" value={d.address} />
          </InfoCard>

          {patient.identifiers?.length > 0 && (
            <InfoCard title="Identifiants">
              {patient.identifiers.map((id, i) => (
                <div key={i} className="flex justify-between text-sm py-1">
                  <span className="text-gray-500">{id.type}</span>
                  <span className="font-mono text-gray-800">{id.value}</span>
                </div>
              ))}
            </InfoCard>
          )}
        </div>

        {/* Right columns — Encounters + Claims */}
        <div className="lg:col-span-2 space-y-6">
          {/* Encounters */}
          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-3">
              Consultations ({encounters.length})
            </h2>
            {encounters.length === 0 ? (
              <div className="bg-white rounded-lg border border-gray-200 p-6 text-center text-sm text-gray-400">
                Aucune consultation enregistrée
              </div>
            ) : (
              <div className="space-y-3">
                {encounters.slice(0, 5).map((enc: any) => (
                  <EncounterCard key={enc.encounter_id} encounter={enc} />
                ))}
              </div>
            )}
          </section>

          {/* Recent Claims */}
          {recentClaims.length > 0 && (
            <section>
              <h2 className="text-base font-semibold text-gray-900 mb-3">
                Alertes & Recommandations récentes
              </h2>
              <div className="space-y-2">
                {recentClaims.map((claim) => (
                  <ClaimCard key={claim.claim_id} claim={claim} />
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </main>
  );
}

function InfoCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
      <div className="px-4 py-3 border-b border-gray-100">
        <h3 className="text-sm font-semibold text-gray-700">{title}</h3>
      </div>
      <div className="px-4 py-3 space-y-1">{children}</div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value?: string }) {
  return (
    <div className="flex justify-between text-sm py-0.5">
      <span className="text-gray-500">{label}</span>
      <span className="text-gray-800">
        {value ?? <span className="text-gray-300">—</span>}
      </span>
    </div>
  );
}

function EncounterCard({ encounter }: { encounter: any }) {
  const statusColors: Record<string, string> = {
    active: "bg-green-100 text-green-700",
    completed: "bg-gray-100 text-gray-600",
    cancelled: "bg-red-100 text-red-600",
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-gray-900">
            {encounter.reason ?? "Consultation"}
          </p>
          <p className="text-xs text-gray-500 mt-0.5">
            {encounter.service ?? encounter.encounter_type} ·{" "}
            {encounter.location ?? "—"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              statusColors[encounter.status] ?? "bg-gray-100 text-gray-600"
            }`}
          >
            {encounter.status}
          </span>
          <span className="text-xs text-gray-400">
            {encounter.start_at
              ? new Date(encounter.start_at).toLocaleDateString("fr-CD")
              : "—"}
          </span>
        </div>
      </div>
    </div>
  );
}

const CRITICALITY_COLORS: Record<string, string> = {
  critical: "border-l-red-500 bg-red-50",
  high: "border-l-orange-500 bg-orange-50",
  moderate: "border-l-yellow-500 bg-yellow-50",
  low: "border-l-blue-500 bg-blue-50",
};

const TYPE_LABELS: Record<string, string> = {
  alert: "Alerte",
  reco: "Recommandation",
  dx: "Diagnostic",
  tx: "Traitement",
  score: "Score",
  info: "Info",
};

function ClaimCard({ claim }: { claim: Claim }) {
  return (
    <div
      className={`bg-white rounded-lg border border-l-4 p-4 shadow-sm ${
        CRITICALITY_COLORS[claim.criticality] ?? "border-l-gray-300"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
              {TYPE_LABELS[claim.type] ?? claim.type}
            </span>
            {claim.status === "blocked" && (
              <span className="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded">
                Bloqué
              </span>
            )}
          </div>
          <p className="text-sm text-gray-900">{claim.text}</p>
          {claim.blocked_reason && (
            <p className="text-xs text-red-600 mt-1">↳ {claim.blocked_reason}</p>
          )}
        </div>
      </div>

      {/* Evidence refs */}
      {claim.evidence_refs?.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {claim.evidence_refs.map((evidenceRef, i) => (
            <EvidenceRefBadge key={i} ref_={evidenceRef} />
          ))}
        </div>
      )}
    </div>
  );
}
