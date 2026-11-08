import type { Metadata } from "next";
import { BenchmarkLab } from "@/components/benchmark/BenchmarkLab";

export const metadata: Metadata = { title: "Benchmark Lab" };

export default function BenchmarkPage() {
  return <BenchmarkLab />;
}
