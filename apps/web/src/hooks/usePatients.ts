import { useQuery } from "@tanstack/react-query";
import { patientsApi } from "@/lib/api";
import type { PaginatedResponse, Patient } from "@/types";

export function usePatients(params?: { page?: number; per_page?: number; q?: string }) {
  return useQuery<PaginatedResponse<Patient>>({
    queryKey: ["patients", params],
    queryFn: () => patientsApi.list(params).then((r) => r.data),
  });
}

export function usePatient(id: string) {
  return useQuery<Patient>({
    queryKey: ["patients", id],
    queryFn: () => patientsApi.get(id).then((r) => r.data),
    enabled: !!id,
  });
}

export function usePatientTimeline(id: string) {
  return useQuery({
    queryKey: ["patients", id, "timeline"],
    queryFn: () => patientsApi.timeline(id).then((r) => r.data),
    enabled: !!id,
  });
}
