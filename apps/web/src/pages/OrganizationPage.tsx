import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { supabase } from "@/lib/supabase";

const ROLES = { owner: "Propietario", admin: "Administrador", member: "Miembro" } as const;
const KINDS = { business: "Negocio", institution: "Institución" } as const;

export function OrganizationPage({ email }: { email: string | undefined }) {
  const { data, error, isPending } = useQuery({
    queryKey: ["me", "organization"],
    queryFn: async () => {
      const { data, error } = await api.GET("/me/organization");
      if (error) throw new Error(error.detail);
      return data;
    },
  });

  return (
    <main className="mx-auto flex min-h-svh max-w-xl flex-col gap-6 px-4 py-10">
      <header className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold">Mi organización</h1>
        <Button variant="outline" onClick={() => supabase.auth.signOut()}>
          Salir
        </Button>
      </header>

      {isPending && <p className="text-muted-foreground">Cargando…</p>}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>No se pudo cargar tu organización: {error.message}</AlertDescription>
        </Alert>
      )}
      {data && (
        <Card>
          <CardHeader>
            <CardTitle>{data.name}</CardTitle>
            <CardDescription>{email}</CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-muted-foreground">Tipo</dt>
                <dd className="font-medium">{KINDS[data.kind]}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Tu rol</dt>
                <dd className="font-medium">{ROLES[data.role]}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-muted-foreground">Créditos disponibles</dt>
                <dd className="text-3xl font-bold tabular-nums">
                  {data.credit_balance.toLocaleString("es-CO")}
                </dd>
              </div>
            </dl>
          </CardContent>
        </Card>
      )}
    </main>
  );
}
