import { PageHeader } from "@/components/AppLayout";
import { Users, Database, Shield, Server } from "lucide-react";

export function AdminPage() {
  return (
    <>
      <PageHeader title="Settings" />
      <div className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-2xl space-y-4">
          <SettingsCard
            icon={Users}
            title="User Management"
            description="Manage team members, roles, and permissions."
          />
          <SettingsCard
            icon={Database}
            title="Unit Cost Database"
            description="Manage regional unit costs and assembly templates."
          />
          <SettingsCard
            icon={Shield}
            title="Organization"
            description="Company details, branding, and default settings."
          />
          <SettingsCard
            icon={Server}
            title="Integrations"
            description="Connect external tools and configure webhooks."
          />
        </div>
      </div>
    </>
  );
}

function SettingsCard({
  icon: Icon,
  title,
  description,
}: {
  icon: typeof Users;
  title: string;
  description: string;
}) {
  return (
    <div className="flex items-center gap-4 rounded-lg border border-gray-200 bg-white p-5 hover:bg-gray-50 cursor-pointer transition-colors">
      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-100">
        <Icon className="h-5 w-5 text-gray-600" />
      </div>
      <div>
        <h3 className="text-sm font-semibold">{title}</h3>
        <p className="text-xs text-gray-500">{description}</p>
      </div>
    </div>
  );
}
