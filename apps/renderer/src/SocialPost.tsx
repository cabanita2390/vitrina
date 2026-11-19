import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { z } from "zod";

export const socialPostSchema = z.object({
  businessName: z.string().min(1).max(80),
  headline: z.string().min(1).max(90),
  body: z.string().max(220).default(""),
  logoUrl: z.string().url().nullable().default(null),
  audioUrl: z.string().url().nullable().default(null),
  primaryColor: z.string().regex(/^#[0-9a-fA-F]{6}$/).default("#7C3AED"),
  accentColor: z.string().regex(/^#[0-9a-fA-F]{6}$/).default("#FBBF24"),
  durationInSeconds: z.number().min(3).max(90).default(8),
});

export type SocialPostProps = z.infer<typeof socialPostSchema>;

const Logo: React.FC<{ url: string | null; name: string; color: string }> = ({
  url,
  name,
  color,
}) => {
  const size = 220;
  if (url) {
    return <Img src={url} style={{ width: size, height: size, objectFit: "contain" }} />;
  }
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        background: "white",
        color,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 120,
        fontWeight: 800,
      }}
    >
      {name.trim().charAt(0).toUpperCase()}
    </div>
  );
};

export const SocialPost: React.FC<SocialPostProps> = (props) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const logoIn = spring({ frame, fps, config: { damping: 14 } });
  const headlineIn = spring({ frame: frame - 12, fps, config: { damping: 18 } });
  const bodyOpacity = interpolate(frame, [30, 50], [0, 1], { extrapolateRight: "clamp" });
  const outro = interpolate(frame, [durationInFrames - 15, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(160deg, ${props.primaryColor} 0%, #111827 100%)`,
        fontFamily: "Inter, Arial, Helvetica, sans-serif",
        color: "white",
        padding: 90,
        justifyContent: "center",
        alignItems: "center",
        textAlign: "center",
        opacity: outro,
      }}
    >
      {props.audioUrl ? <Audio src={props.audioUrl} /> : null}
      <div style={{ transform: `scale(${logoIn})`, marginBottom: 80 }}>
        <Logo url={props.logoUrl} name={props.businessName} color={props.primaryColor} />
      </div>
      <h1
        style={{
          fontSize: 96,
          lineHeight: 1.05,
          margin: 0,
          fontWeight: 800,
          transform: `translateY(${(1 - headlineIn) * 80}px)`,
          opacity: headlineIn,
        }}
      >
        {props.headline}
      </h1>
      <div
        style={{
          width: 160,
          height: 12,
          borderRadius: 6,
          background: props.accentColor,
          margin: "60px 0",
          transform: `scaleX(${headlineIn})`,
        }}
      />
      <p style={{ fontSize: 52, lineHeight: 1.3, margin: 0, opacity: bodyOpacity }}>{props.body}</p>
      <p
        style={{
          position: "absolute",
          bottom: 120,
          fontSize: 44,
          fontWeight: 700,
          letterSpacing: 2,
          opacity: bodyOpacity,
        }}
      >
        {props.businessName}
      </p>
    </AbsoluteFill>
  );
};
