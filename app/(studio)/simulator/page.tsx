import PageContainer from "../../../components/ui/PageContainer";
import LineupGridPlaceholder from "../../../components/ui/LineupGridPlaceholder";

export default function SimulatorPage() {
  return (
    <PageContainer title="Simulator">
      <LineupGridPlaceholder label="Simulator Grid" />
      <div className="mt-4 text-sm opacity-70">Export to DK Entries button will live here.</div>
    </PageContainer>
  );
}

