export function getToken(): string | null {
  return localStorage.getItem("aurum_token");
}

export function setToken(token: string): void {
  localStorage.setItem("aurum_token", token);
}

export function clearToken(): void {
  localStorage.removeItem("aurum_token");
}

export function isAuthenticated(): boolean {
  return !!getToken();
}
