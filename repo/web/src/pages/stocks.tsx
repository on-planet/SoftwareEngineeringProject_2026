import type { GetServerSideProps } from "next";

export const getServerSideProps: GetServerSideProps = async () => ({
  redirect: {
    destination: "/stocks/a",
    permanent: false,
  },
});

export default function StocksEntryPage() {
  return null;
}
