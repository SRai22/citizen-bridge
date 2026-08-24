export function GET() {
  return Response.json({
    categories: [
      {
        id: "father_death",
        title: "Someone Passed Away",
        description: "Get a clear plan for certificates, pensions and household services.",
      },
    ],
  });
}
