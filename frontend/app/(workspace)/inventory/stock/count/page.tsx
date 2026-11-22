import {redirect} from "next/navigation";
export default function Count(){redirect("/inventory/stock/adjust?kind=count")}
