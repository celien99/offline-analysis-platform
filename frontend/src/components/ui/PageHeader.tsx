import type { ReactNode } from "react";
import { Row, Col } from "antd";

interface Props {
  title: string;
  extra?: ReactNode;
}

export default function PageHeader({ title, extra }: Props) {
  return (
    <Row justify="space-between" align="middle" className="mb-4">
      <Col>
        <h2 className="text-lg font-semibold">{title}</h2>
      </Col>
      {extra && <Col>{extra}</Col>}
    </Row>
  );
}
