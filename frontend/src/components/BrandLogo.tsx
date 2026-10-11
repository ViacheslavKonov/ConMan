type BrandVariant = "stacked" | "horizontal" | "mark";

const assets: Record<BrandVariant, { file: string; width: number; height: number }> = {
  stacked: { file: "conman-lockup-stacked.svg", width: 440, height: 385 },
  horizontal: { file: "conman-lockup-horizontal.svg", width: 580, height: 160 },
  mark: { file: "conman-mark.svg", width: 200, height: 200 },
};

export default function BrandLogo({
  variant = "horizontal",
  className = "",
  decorative = false,
}: {
  variant?: BrandVariant;
  className?: string;
  decorative?: boolean;
}) {
  const asset = assets[variant];
  return (
    <img
      className={`brand-logo brand-logo--${variant} ${className}`.trim()}
      src={`/brand/${asset.file}`}
      width={asset.width}
      height={asset.height}
      alt={decorative ? "" : "ConMan — Convention Management"}
      draggable={false}
    />
  );
}
