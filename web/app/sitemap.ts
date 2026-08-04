import type { MetadataRoute } from "next";

const sessions = [
  "us_video3", "us_video1", "us_video2_vision", "us_aggression",
  "it_carabinieri_arrest", "nl_politie_inval", "es_robbery_shootout",
];

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: "https://sentinel-audit.co/", priority: 1 },
    { url: "https://sentinel-audit.co/demo", priority: 0.9 },
    ...sessions.map((id) => ({
      url: `https://sentinel-audit.co/demo/${id}`,
      priority: 0.7,
    })),
  ];
}