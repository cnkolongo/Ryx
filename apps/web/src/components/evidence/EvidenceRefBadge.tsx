"use client";

/**
 * EvidenceRefBadge — Affiche une preuve cliquable.
 *
 * Design principle : toute preuve doit être cliquable et ouvrir le viewer.
 * C'est le coeur UX de RYX (evidence-first).
 */

import type { EvidenceRef } from "@/types";

interface EvidenceRefBadgeProps {
  ref_: EvidenceRef;
  onClick?: (ref: EvidenceRef) => void;
}

export function EvidenceRefBadge({ ref_, onClick }: EvidenceRefBadgeProps) {
  const label = getRefLabel(ref_);
  const icon = getRefIcon(ref_);
  const confidence = Math.round(ref_.confidence * 100);

  return (
    <button
      onClick={() => onClick?.(ref_)}
      className="inline-flex items-center gap-1.5 px-2 py-1 text-xs rounded-md
                 bg-blue-50 text-blue-700 border border-blue-200
                 hover:bg-blue-100 transition-colors cursor-pointer"
      title={`Preuve: ${label} (confiance: ${confidence}%)`}
    >
      <span>{icon}</span>
      <span className="font-medium">{label}</span>
      <span className="text-blue-400">{confidence}%</span>
    </button>
  );
}

function getRefLabel(ref: EvidenceRef): string {
  switch (ref.kind) {
    case "doc":
      return `Doc p.${ref.page}`;
    case "dicom":
      return `DICOM ${ref.instance_or_slice}`;
    case "lab":
      return `${ref.test}: ${ref.value}${ref.unit ? ` ${ref.unit}` : ""}`;
    case "knowledge":
      return ref.title || `Knowledge Doc`;
  }
}

function getRefIcon(ref: EvidenceRef): string {
  switch (ref.kind) {
    case "doc": return "📄";
    case "dicom": return "🩻";
    case "lab": return "🧪";
    case "knowledge": return "📚";
  }
}

// ─── Claim avec preuves ───────────────────────────────────────────────────────

import type { Claim } from "@/types";

interface ClaimCardProps {
  claim: Claim;
  onEvidenceClick?: (ref: EvidenceRef) => void;
}

export function ClaimCard({ claim, onEvidenceClick }: ClaimCardProps) {
  const statusClass = {
    valid: "border-green-200 bg-green-50",
    blocked: "border-red-200 bg-red-50",
    pending: "border-gray-200 bg-gray-50",
    needs_human: "border-amber-200 bg-amber-50",
  }[claim.status];

  const criticalityClass = {
    critical: "text-red-700 font-bold",
    high: "text-orange-700 font-semibold",
    moderate: "text-amber-700",
    low: "text-green-700",
  }[claim.criticality];

  return (
    <div className={`rounded-lg border p-4 ${statusClass}`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <p className={`text-sm ${criticalityClass}`}>{claim.text}</p>
        <div className="flex gap-1.5 flex-shrink-0">
          <StatusBadge status={claim.status} />
          <CriticalityBadge criticality={claim.criticality} />
        </div>
      </div>

      {claim.blocked_reason && (
        <p className="text-xs text-red-600 mb-2 italic">{claim.blocked_reason}</p>
      )}

      {claim.evidence_refs.length > 0 ? (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {claim.evidence_refs.map((ref, i) => (
            <EvidenceRefBadge key={i} ref_={ref} onClick={onEvidenceClick} />
          ))}
        </div>
      ) : (
        <p className="text-xs text-gray-400 italic mt-1">
          ⚠ Aucune preuve — bloqué par EvidenceGuard
        </p>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: Claim["status"] }) {
  const labels = {
    valid: ["✓ Validé", "bg-green-100 text-green-700"],
    blocked: ["✗ Bloqué", "bg-red-100 text-red-700"],
    pending: ["… En attente", "bg-gray-100 text-gray-600"],
    needs_human: ["! Révision", "bg-amber-100 text-amber-700"],
  };
  const [label, cls] = labels[status];
  return <span className={`text-xs px-2 py-0.5 rounded ${cls}`}>{label}</span>;
}

function CriticalityBadge({ criticality }: { criticality: Claim["criticality"] }) {
  const labels = {
    critical: ["CRITIQUE", "badge-critical"],
    high: ["ÉLEVÉ", "badge-high"],
    moderate: ["MODÉRÉ", "badge-moderate"],
    low: ["FAIBLE", "badge-low"],
  };
  const [label, cls] = labels[criticality];
  return <span className={`text-xs px-2 py-0.5 rounded ${cls}`}>{label}</span>;
}
