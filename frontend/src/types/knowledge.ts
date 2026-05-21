export interface KnowledgeEntry {
  knowledge_id: string;
  cluster_id: string | null;
  category: string;
  defect_type: string | null;
  title: string;
  description: string | null;
  action: string;
  camera_ids: string[];
  created_at: string;
}
