import React from "react";

import { EventTimelineList } from "../components/EventTimelineList";
import { IndexConstituentList } from "../components/IndexConstituentList";
import { NewsAggregateList } from "../components/NewsAggregateList";
import { SectorExposurePanel } from "../components/SectorExposurePanel";

const TEXT = {
  news: "新闻聚合",
  events: "事件时间线",
  constituents: "指数成分股",
  exposure: "行业暴露",
};

export default function InsightsPage() {
  return (
    <div className="page">
      <section>
        <h2 className="section-title">{TEXT.news}</h2>
        <div className="card">
          <NewsAggregateList />
        </div>
      </section>
      <section>
        <h2 className="section-title">{TEXT.events}</h2>
        <div className="card">
          <EventTimelineList />
        </div>
      </section>
      <section>
        <h2 className="section-title">{TEXT.constituents}</h2>
        <div className="card">
          <IndexConstituentList />
        </div>
      </section>
      <section>
        <h2 className="section-title">{TEXT.exposure}</h2>
        <div className="card">
          <SectorExposurePanel />
        </div>
      </section>
    </div>
  );
}
