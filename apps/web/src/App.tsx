import { useSession } from "@/hooks/useSession";
import { LoginPage } from "@/pages/LoginPage";
import { OrganizationPage } from "@/pages/OrganizationPage";

export default function App() {
  const session = useSession();
  if (session === undefined) return null;
  if (!session) return <LoginPage />;
  return <OrganizationPage email={session.user.email} />;
}
