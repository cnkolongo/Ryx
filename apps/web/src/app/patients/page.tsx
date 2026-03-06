"use client";

import { useState } from "react";
import Link from "next/link";
import { usePatients } from "@/hooks/usePatients";
import type { Patient } from "@/types";

export default function PatientsPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = usePatients({
    page,
    per_page: 20,
    q: search || undefined,
  });

  return (
    <main className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Patients</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {data?.pagination.total ?? "—"} patients enregistrés
          </p>
        </div>
        <Link
          href="/patients/new"
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          + Nouveau patient
        </Link>
      </div>

      {/* Search bar */}
      <div className="mb-4">
        <input
          type="text"
          placeholder="Rechercher par nom, prénom, MRN..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="w-full border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-gray-400">
            Chargement...
          </div>
        ) : isError ? (
          <div className="p-8 text-center text-sm text-red-500">
            Erreur lors du chargement des patients
          </div>
        ) : (data?.data?.length ?? 0) === 0 ? (
          <div className="p-8 text-center text-sm text-gray-400">
            {search ? `Aucun résultat pour "${search}"` : "Aucun patient enregistré"}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="text-left px-4 py-3 font-medium text-gray-600">Nom</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Prénom</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Date naissance</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Téléphone</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">ID</th>
                <th className="w-16" />
              </tr>
            </thead>
            <tbody>
              {data?.data.map((patient) => (
                <PatientRow key={patient.patient_id} patient={patient} />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {data && data.pagination.total_pages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-gray-500">
            Page {data.pagination.page} / {data.pagination.total_pages}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1 rounded border text-sm disabled:opacity-40 hover:bg-gray-50"
            >
              ← Précédent
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= data.pagination.total_pages}
              className="px-3 py-1 rounded border text-sm disabled:opacity-40 hover:bg-gray-50"
            >
              Suivant →
            </button>
          </div>
        </div>
      )}
    </main>
  );
}

function PatientRow({ patient }: { patient: Patient }) {
  const d = patient.demographics ?? {};
  return (
    <tr className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
      <td className="px-4 py-3 font-medium text-gray-900">
        {d.last_name ?? <span className="text-gray-300">—</span>}
      </td>
      <td className="px-4 py-3 text-gray-700">
        {d.first_name ?? <span className="text-gray-300">—</span>}
      </td>
      <td className="px-4 py-3 text-gray-500">
        {d.date_of_birth
          ? new Date(d.date_of_birth).toLocaleDateString("fr-CD")
          : <span className="text-gray-300">—</span>}
      </td>
      <td className="px-4 py-3 text-gray-500">
        {d.phone ?? <span className="text-gray-300">—</span>}
      </td>
      <td className="px-4 py-3 text-gray-400 font-mono text-xs">
        {patient.patient_id.slice(0, 8)}…
      </td>
      <td className="px-4 py-3">
        <Link
          href={`/patients/${patient.patient_id}`}
          className="text-blue-600 hover:underline text-xs font-medium"
        >
          Dossier →
        </Link>
      </td>
    </tr>
  );
}
