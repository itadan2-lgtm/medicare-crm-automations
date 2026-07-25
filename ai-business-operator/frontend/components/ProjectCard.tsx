import Link from 'next/link';
import type { Project } from '@/lib/api';

const STATUS_DOT: Record<string, string> = {
  active: 'bg-blue-500',
  paused: 'bg-slate-400',
  blocked: 'bg-red-500',
  completed: 'bg-green-500',
};

export function ProjectCard({ project }: { project: Project }) {
  return (
    <Link
      href={`/projects/${project.project_id}`}
      className="block rounded-lg border border-slate-200 bg-white p-4 transition hover:border-slate-300 hover:shadow-sm"
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-semibold text-slate-900">{project.name}</h3>
        <span className="flex items-center gap-1.5 text-xs text-slate-500">
          <span
            className={`h-2 w-2 rounded-full ${STATUS_DOT[project.status] ?? 'bg-slate-300'}`}
          />
          {project.status}
        </span>
      </div>
      <p className="mt-2 line-clamp-2 text-sm text-slate-600">{project.goal}</p>
      {project.niche && (
        <span className="mt-3 inline-block rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
          {project.niche}
        </span>
      )}
    </Link>
  );
}
