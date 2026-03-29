import React from "react";

import { EventTimelineList } from "../components/EventTimelineList";
import { IndexDecompositionPanel } from "../components/IndexDecompositionPanel";
import { NewsAggregateList } from "../components/NewsAggregateList";
import { NewsRelationGraph } from "../components/NewsRelationGraph";
import { SectorExposurePanel } from "../components/SectorExposurePanel";

export default function InsightsPage() {
  return (
    <div className="page">
      <section>
        <h2 className="section-title">新闻关系图谱</h2>
        <NewsRelationGraph />
      </section>

      <section>
        <h2 className="section-title">指数拆解</h2>
        <IndexDecompositionPanel />
      </section>

      <section>
        <h2 className="section-title">聚合新闻</h2>
        <div className="card">
          <NewsAggregateList />
        </div>
      </section>

      <section>
        <h2 className="section-title">事件时间线</h2>
        <div className="card">
          <EventTimelineList />
        </div>
      </section>

      <section>
        <h2 className="section-title">行业暴露</h2>
        <div className="card">
          <SectorExposurePanel />
        </div>
      </section>
    </div>
  );
}
