import { Image, Space } from "antd";

interface Props {
  images: { url: string; label?: string }[];
}

export default function ImageViewer({ images }: Props) {
  return (
    <Space wrap>
      {images.map((img, i) => (
        <div key={i} style={{ textAlign: "center" }}>
          {img.label && <div style={{ marginBottom: 4 }}>{img.label}</div>}
          <Image
            src={img.url}
            alt={img.label || `Image ${i + 1}`}
            width={150}
            style={{ objectFit: "cover", borderRadius: 4 }}
            fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
          />
        </div>
      ))}
    </Space>
  );
}
