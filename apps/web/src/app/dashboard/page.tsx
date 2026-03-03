"use client";

import { usePatients } from "@/hooks/usePatients";
import { useNotifications } from "@/hooks/useNotifications";

export default function DashboardPage() {
  return (
    <main className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Tableau de bord RYX</h1>
        <p className="text-gray-500 text-sm mt-1">
          Filet de sécurité clinique — Evidence-first
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <StatCard title="Patients actifs" value="—" />
        <StatCard title="Alertes non lues" value="—" badge="new" />
        <StatCard title="Rapports générés (24h)" value="—" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RecentAlerts />
        <RecentPatients />
      </div>
    </main>
  );
}

function StatCard({
  title,
  value,
  badge,
}: {
  title: string;
  value: string;
  badge?: string;
}) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">{title}</p>
        {badge && (
          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
            {badge}
          </span>
        )}
      </div>
      <p className="text-2xl font-bold mt-1 text-gray-900">{value}</p>
    </div>
  );
}

function RecentAlerts() {
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
      <div className="p-4 border-b border-gray-100">
        <h2 className="font-semibold text-gray-900">Alertes récentes</h2>
        <p className="text-xs text-gray-400 mt-0.5">
          Toutes les alertes ont une preuve cliquable (EvidenceGuard)
        </p>
      </div>
      <div className="p-4">
        <p className="text-sm text-gray-400 text-center py-8">
          Aucune alerte — chargement des données...
        </p>
      </div>
    </div>
  );
}

function RecentPatients() {
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
      <div className="p-4 border-b border-gray-100">
        <h2 className="font-semibold text-gray-900">Patients récents</h2>
      </div>
      <div className="p-4">
        <p className="text-sm text-gray-400 text-center py-8">
          Chargement...
        </p>
      </div>
    </div>
  );
}
