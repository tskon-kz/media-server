import {
  AlertTriangle, ArrowDown, ArrowUp, CheckCircle2, Clock,
  HardDrive, HelpCircle, Leaf, Package, Pause, RefreshCw,
  Search, XCircle, type LucideProps,
} from "lucide-react";
import type { ComponentType } from "react";

const STATE_ICONS: Record<string, ComponentType<LucideProps>> = {
  downloading: ArrowDown,
  forcedDL: ArrowDown,
  stalledDL: RefreshCw,
  metaDL: Search,
  allocating: HardDrive,
  checkingDL: Search,
  checkingResumeData: Search,
  checkingUP: Search,
  queuedDL: Clock,
  queuedUP: Clock,
  uploading: ArrowUp,
  forcedUP: ArrowUp,
  stalledUP: Leaf,
  seeding: Leaf,
  pausedDL: Pause,
  pausedUP: CheckCircle2,
  // qBittorrent 5.x renamed pausedDL/pausedUP -> stoppedDL/stoppedUP
  stoppedDL: Pause,
  stoppedUP: CheckCircle2,
  moving: Package,
  missingFiles: AlertTriangle,
  error: XCircle,
  unknown: HelpCircle,
};

export function TorrentIcon({ state, size = 22 }: { state: string; size?: number }) {
  const Icon = STATE_ICONS[state] ?? HelpCircle;
  return <Icon size={size} />;
}
