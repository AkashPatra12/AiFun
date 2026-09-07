import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { UploadControl } from "@/components/UploadControl";
import { StatusTable } from "@/components/StatusTable";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-10">
        <h1 className="text-2xl font-semibold text-neutral-900">AiFun</h1>
        <UploadControl />
        <StatusTable />
      </div>
    </QueryClientProvider>
  );
}
