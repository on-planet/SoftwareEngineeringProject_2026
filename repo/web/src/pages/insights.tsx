import React from "react";

import { EventTimelineList } from "../components/EventTimelineList";
import { IndexConstituentList } from "../components/IndexConstituentList";
import { NewsAggregateList } from "../components/NewsAggregateList";
import { SectorExposurePanel } from "../components/SectorExposurePanel";

const TEXT = {
  news: "\u65b0\u95fb\u805a\u5408",
  events: "\u4e8b\u4ef6\u65f6\u95f4\u7ebf",
  constituents: "\u6307\u6570\u6210\u5206\u80a1",
  exposure: "\u884c\u4e1a\u66b4\u9732",
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
