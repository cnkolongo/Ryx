import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { notificationsApi } from "@/lib/api";
import type { Notification } from "@/types";

export function useNotifications() {
  return useQuery<{ data: Notification[] }>({
    queryKey: ["notifications"],
    queryFn: () => notificationsApi.list().then((r) => r.data),
    refetchInterval: 30000, // Poll toutes les 30s si WS indisponible
  });
}

/**
 * Hook WebSocket pour notifications temps réel.
 * Fallback sur polling si WS non disponible (edge offline).
 */
export function useNotificationsWS(onMessage: (notification: Notification) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("ryx_access_token");
    if (!token) return;

    const wsUrl = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/api/notifications/feed?token=${token}`;

    try {
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => setConnected(true);
      wsRef.current.onclose = () => setConnected(false);
      wsRef.current.onmessage = (event) => {
        try {
          const notification = JSON.parse(event.data) as Notification;
          onMessage(notification);
        } catch {
          // Message non-JSON ignoré (ping/pong)
        }
      };

      // Ping toutes les 30s pour garder la connexion
      const pingInterval = setInterval(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send("ping");
        }
      }, 30000);

      return () => {
        clearInterval(pingInterval);
        wsRef.current?.close();
      };
    } catch {
      // WS non supporté ou offline → polling fallback
      setConnected(false);
    }
  }, [onMessage]);

  return { connected };
}
