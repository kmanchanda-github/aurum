import { useQuery } from "@tanstack/react-query";
import { authApi } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";

export function useAdminAuth() {
  const { data, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: () => authApi.me().then((r) => r.data),
    enabled: isAuthenticated(),
    staleTime: 5 * 60 * 1000,
  });

  return {
    isAdmin: data?.is_admin === true,
    isLoading,
    user: data,
  };
}
