import React from "react";
import { Composition } from "remotion";
import { SocialPost, socialPostSchema } from "./SocialPost";

const FPS = 30;

export const RemotionRoot: React.FC = () => (
  <Composition
    id="SocialPost"
    component={SocialPost}
    schema={socialPostSchema}
    width={1080}
    height={1920}
    fps={FPS}
    durationInFrames={8 * FPS}
    defaultProps={socialPostSchema.parse({
      businessName: "Panadería La Espiga",
      headline: "Almojábanas 2x1",
      body: "Todos los martes en Sogamoso. ¡Te esperamos!",
    })}
    calculateMetadata={({ props }) => ({
      durationInFrames: Math.round(props.durationInSeconds * FPS),
    })}
  />
);
