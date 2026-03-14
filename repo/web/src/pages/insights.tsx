import React from "react";

import { EventTimelineList } from "../components/EventTimelineList";
import { IndexConstituentList } from "../components/IndexConstituentList";
import { NewsAggregateList } from "../components/NewsAggregateList";
import { SectorExposurePanel } from "../components/SectorExposurePanel";

export default function InsightsPage() {
  return (
    <div className="page">
      <section>
        <h2 className="section-title">新闻聚合</h2>
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
        <h2 className="section-title">指数成分股</h2>
        <div className="card">
          <IndexConstituentList />
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
