import { Skeleton, Card, Row, Col } from "antd";

/** 表格页骨架屏 */
export function TableSkeleton() {
  return (
    <Card classNames={{ body: "p-4" }}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Row key={i} gutter={16} className="mb-3">
          <Col span={4}><Skeleton.Input active size="small" block /></Col>
          <Col span={4}><Skeleton.Input active size="small" block /></Col>
          <Col span={8}><Skeleton.Input active size="small" block /></Col>
          <Col span={4}><Skeleton.Button active size="small" block /></Col>
          <Col span={4}><Skeleton.Button active size="small" block /></Col>
        </Row>
      ))}
    </Card>
  );
}

/** 卡片网格页骨架屏 */
export function CardGridSkeleton({ count = 6 }: { count?: number }) {
  return (
    <Row gutter={[16, 16]}>
      {Array.from({ length: count }).map((_, i) => (
        <Col key={i} xs={24} sm={12} md={8} lg={6}>
          <Card>
            <Skeleton.Image active className="w-full h-40" />
            <Skeleton active paragraph={{ rows: 2 }} className="mt-3" />
          </Card>
        </Col>
      ))}
    </Row>
  );
}

/** 统计卡片骨架屏 */
export function StatsSkeleton() {
  return (
    <Row gutter={[16, 16]}>
      {[1, 2, 3, 4].map((i) => (
        <Col key={i} span={6}>
          <Card>
            <Skeleton.Input active size="small" className="w-16 mb-2" />
            <Skeleton.Input active size="large" className="w-24" />
          </Card>
        </Col>
      ))}
    </Row>
  );
}
