"use client";

import Link from "next/link";
import { usePatients } from "@/hooks/usePatients";
import { useNotifications } from "@/hooks/useNotifications";
import type { Notification, Patient } from "@/types";

export default function DashboardPage() {
  const { data: patientsData } = usePatients({ per_page: 5 });
  const { data: notificationsData } = useNotifications();

  const totalPatients = patientsData?.pagination?.total;
  const recentPatients = patientsData?.data ?? [];

  const notifications = notificationsData?.data ?? [];
  const unreadAlerts = notifications.filter(
    (n) => !n.read && n.type === "alert"
  ).length;

  const reportsToday = notifications.filter(
    (n) =>
      n.type === "report_ready" &&
      new Date(n.created_at).toDateString() === new Date().toDateString()
  ).length;

  return (
    <main className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Tableau de bord RYX</h1>
        <p className="text-gray-500 text-sm mt-1">
          Filet de sécurité clinique — Evidence-first
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <StatCard
          title="Patients actifs"
          value={totalPatients != null ? String(totalPatients) : "—"}
          href="/patients"
        />
        <StatCard
          title="Alertes non lues"
          value={String(unreadAlerts)}
          badge={unreadAlerts > 0 ? "new" : undefined}
        />
        <StatCard
          title="Rapports générés (24h)"
          value={String(reportsToday)}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RecentAlerts
          notifications={notifications
            .filter((n) => n.type === "alert")
            .slice(0, 5)}
        />
        <RecentPatients patients={recentPatients} />
      </div>
    </main>
  );
}

function StatCard({
  title,
  value,
  badge,
  href,
}: {
  title: string;
  value: string;
  badge?: string;
  href?: string;
}) {
  const inner = (
    <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm hover:shadow-md transition-shadow">
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

  if (href) {
    return <Link href={href}>{inner}</Link>;
  }
  return inner;
}

function RecentAlerts({ notifications }: { notifications: Notification[] }) {
  const critColors: Record<string, string> = {
    critical: "bg-red-100 text-red-700",
    high: "bg-orange-100 text-orange-700",
    moderate: "bg-yellow-100 text-yellow-700",
    low: "bg-blue-100 text-blue-700",
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
      <div className="p-4 border-b border-gray-100">
        <h2 className="font-semibold text-gray-900">Alertes récentes</h2>
        <p className="text-xs text-gray-400 mt-0.5">
          Toutes les alertes ont une preuve cliquable (EvidenceGuard)
        </p>
      </div>
      <div className="p-4">
        {notifications.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-8">Aucune alerte</p>
        ) : (
          <div className="space-y-2">
            {notifications.map((n) => (
              <div
                key={n.id}
                className="flex items-start gap-3 py-2 border-b border-gray-50 last:border-0"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-800 truncate">{n.payload.message}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {new Date(n.created_at).toLocaleString("fr-CD")}
                  </p>
                </div>
                {n.payload.criticality && (
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full flex-shrink-0 ${
                      critColors[n.payload.criticality] ?? "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {n.payload.criticality}
                  </span>
                )}
                {!n.read && (
                  <div className="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0 mt-1.5" />
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function RecentPatients({ patients }: { patients: Patient[] }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
      <div className="p-4 border-b border-gray-100 flex items-center justify-between">
        <h2 className="font-semibold text-gray-900">Patients récents</h2>
        <Link href="/patients" className="text-xs text-blue-600 hover:underline">
          Voir tous →
        </Link>
      </div>
      <div className="p-4">
        {patients.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-8">Aucun patient</p>
        ) : (
          <div className="space-y-1">
            {patients.map((patient) => {
              const d = patient.demographics ?? {};
              return (
                <Link
                  key={patient.patient_id}
                  href={`/patients/${patient.patient_id}`}
                  className="flex items-center justify-between py-2 px-2 rounded hover:bg-gray-50 transition-colors"
                >
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {d.last_name} {d.first_name}
                    </p>
                    <p className="text-xs text-gray-400 font-mono">
                      {patient.patient_id.slice(0, 8)}…
                    </p>
                  </div>
                  <span className="text-xs text-gray-400">
                    {new Date(patient.updated_at).toLocaleDateString("fr-CD")}
                  </span>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
