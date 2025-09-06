import { redirect } from "next/navigation";

export default function Page() {
  // Default to Optimizer tab
  redirect("/optimizer");
}

