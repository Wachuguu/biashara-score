import {
  CircleHelp,
  HandCoins,
  House,
  Package,
  ShoppingBasket,
  Smartphone,
  Wallet,
  Zap,
  type LucideIcon,
} from "lucide-react";
import type { Category } from "@/api/types";

export interface CategoryMeta {
  label: string;
  sw: string; // Swahili helper word
  icon: LucideIcon;
  /** Tailwind classes for the chip */
  chip: string;
}

export const CATEGORY_META: Record<Category, CategoryMeta> = {
  SALES: { label: "Sales", sw: "Mauzo", icon: ShoppingBasket, chip: "bg-leaf-soft text-leaf border-leaf/40" },
  INVENTORY: { label: "Stock", sw: "Bidhaa", icon: Package, chip: "bg-cobalt-soft text-cobalt-deep border-cobalt/40" },
  UTILITIES: { label: "Power & water", sw: "Stima, maji", icon: Zap, chip: "bg-maize-soft text-ink border-maize-deep/60" },
  RENT: { label: "Rent", sw: "Kodi", icon: House, chip: "bg-maize-soft text-ink border-maize-deep/60" },
  DEBT_RECOVERY: { label: "Debt repaid", sw: "Debt repaid", icon: HandCoins, chip: "bg-leaf-soft text-leaf border-leaf/40" },
  OWNER_DRAW: { label: "Owner's use", sw: "Matumizi yangu", icon: Wallet, chip: "bg-chili-soft text-chili border-chili/40" },
  AIRTIME: { label: "Airtime", sw: "Airtime", icon: Smartphone, chip: "bg-cobalt-soft text-cobalt-deep border-cobalt/40" },
  UNCATEGORIZED: { label: "Not sorted", sw: "Haijapangwa", icon: CircleHelp, chip: "bg-paper text-ink-soft border-ink/30 border-dashed" },
};
