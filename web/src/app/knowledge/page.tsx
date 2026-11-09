import type { Metadata } from "next";
import { KnowledgeBase } from "@/components/knowledge/KnowledgeBase";

export const metadata: Metadata = { title: "Base de Conocimiento · Knowledge Base" };

export default function KnowledgePage() {
  return <KnowledgeBase />;
}
